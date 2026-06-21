#!/usr/bin/env python3
"""
Genie — VPS Disk Guardian
Safe cleanup of Hermes VPS disk space without reducing functionality.

Tiers:
  Tier 1 (zero risk):  State snapshots, log rotation, cron output compression
  Tier 2 (low risk):   Session JSON compression (duplicates of state.db data)
  Tier 3 (read-only):  state.db bloat analysis, commons/ analysis

Usage:
  python3 genie.py --assess                    # Show current disk state and targets
  python3 genie.py --assess --tier 3           # Include Tier 3 analysis
  python3 genie.py --clean                     # Execute Tier 1+2 cleanup
  python3 genie.py --clean --tier 1            # Only Tier 1
  python3 genie.py --clean --dry-run           # Preview without modifying anything
  python3 genie.py --analyze                   # Tier 3 analysis only
  python3 genie.py --json                      # Output as JSON
"""

import argparse
import datetime
import gzip
import json
import os
import shutil
import sqlite3
import sys

# ── Configuration ──────────────────────────────────────────────────────────

HERMES_HOME = os.environ.get("HERMES_HOME", "/root/.hermes")

DEFAULTS = {
    "snapshot_max_age_days": int(os.environ.get("GENIE_SNAPSHOT_MAX_AGE_DAYS", 7)),
    "log_compress_age_days": int(os.environ.get("GENIE_LOG_COMPRESS_AGE_DAYS", 7)),
    "log_delete_age_days": int(os.environ.get("GENIE_LOG_DELETE_AGE_DAYS", 30)),
    "cron_output_compress_age_days": int(os.environ.get("GENIE_CRON_OUTPUT_COMPRESS_AGE_DAYS", 7)),
    "session_compress_age_days": int(os.environ.get("GENIE_SESSION_COMPRESS_AGE_DAYS", 14)),
    "dry_run": os.environ.get("GENIE_DRY_RUN", "false").lower() == "true",
    "tier_limit": os.environ.get("GENIE_TIER_LIMIT", "3"),
    "state_db_path": os.environ.get("GENIE_STATE_DB_PATH", os.path.join(HERMES_HOME, "state.db")),
    "sessions_path": os.environ.get("GENIE_SESSIONS_PATH", os.path.join(HERMES_HOME, "sessions")),
    "logs_path": os.environ.get("GENIE_LOGS_PATH", os.path.join(HERMES_HOME, "logs")),
    "cron_output_path": os.environ.get("GENIE_CRON_OUTPUT_PATH", os.path.join(HERMES_HOME, "cron", "output")),
    "snapshots_path": os.environ.get("GENIE_SNAPSHOTS_PATH", os.path.join(HERMES_HOME, "state-snapshots")),
    "commons_path": os.environ.get("GENIE_COMMONS_PATH", os.path.join(HERMES_HOME, "commons")),
}

# ── Helpers ────────────────────────────────────────────────────────────────

def du(path):
    if os.path.isfile(path):
        return os.path.getsize(path)
    total = 0
    for dp, _, fnames in os.walk(path):
        for f in fnames:
            fp = os.path.join(dp, f)
            if os.path.isfile(fp):
                total += os.path.getsize(fp)
    return total


def fmt(size_bytes):
    b = float(size_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if abs(b) < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} TB"


def disk_usage():
    stat = os.statvfs("/")
    total = stat.f_blocks * stat.f_frsize
    free = stat.f_bavail * stat.f_frsize
    used = total - free
    return total, used, free, used / total * 100


def age_days(path):
    return (datetime.datetime.now().timestamp() - os.path.getmtime(path)) / 86400


def gzip_file(src, dry_run):
    dst = src + ".gz"
    if os.path.exists(dst):
        return 0
    if dry_run:
        return int(os.path.getsize(src) * 0.9) if os.path.isfile(src) else 0
    if not os.path.isfile(src) or os.path.getsize(src) == 0:
        return 0
    try:
        size_before = os.path.getsize(src)
        with open(src, "rb") as f_in:
            with gzip.open(dst, "wb", compresslevel=6) as f_out:
                shutil.copyfileobj(f_in, f_out)
        if os.path.exists(dst) and os.path.getsize(dst) > 0:
            os.remove(src)
            return size_before - os.path.getsize(dst)
        if os.path.exists(dst):
            os.remove(dst)
        return 0
    except Exception:
        if os.path.exists(dst):
            try:
                os.remove(dst)
            except Exception:
                pass
        return 0


def oldest_mtime_in_dir(dir_path):
    """Return the oldest mtime of any file inside dir_path (recursive)."""
    oldest = os.path.getmtime(dir_path)
    for dp, _, fns in os.walk(dir_path):
        for fn in fns:
            fp = os.path.join(dp, fn)
            if os.path.isfile(fp):
                m = os.path.getmtime(fp)
                if m < oldest:
                    oldest = m
    return oldest


# ── Tier 1: Zero Risk ──────────────────────────────────────────────────────

def clean_snapshots(snapshots_path, max_age_days, dry_run):
    result = {"action": "snapshots", "tier": 1, "files": 0, "bytes_freed": 0, "errors": []}
    if not os.path.isdir(snapshots_path):
        return result

    for entry in os.listdir(snapshots_path):
        path = os.path.join(snapshots_path, entry)
        if not os.path.isdir(path):
            continue
        oldest = oldest_mtime_in_dir(path)
        snap_age = (datetime.datetime.now().timestamp() - oldest) / 86400
        if snap_age > max_age_days:
            size = du(path)
            result["files"] += 1
            result["bytes_freed"] += size
            if not dry_run:
                try:
                    shutil.rmtree(path)
                except Exception as e:
                    result["errors"].append(f"rmtree {path}: {e}")
                    result["bytes_freed"] -= size
    return result


def clean_logs(logs_path, compress_age_days, delete_age_days, dry_run):
    result = {"action": "logs", "tier": 1, "compressed": 0, "deleted": 0,
              "bytes_freed": 0, "errors": []}
    if not os.path.isdir(logs_path):
        return result

    for entry in os.listdir(logs_path):
        path = os.path.join(logs_path, entry)
        if not os.path.isfile(path):
            continue

        if entry.endswith(".gz"):
            if age_days(path) > delete_age_days:
                size = os.path.getsize(path)
                result["deleted"] += 1
                result["bytes_freed"] += size
                if not dry_run:
                    try:
                        os.remove(path)
                    except Exception as e:
                        result["errors"].append(f"remove {path}: {e}")
            continue

        if entry.endswith(".log") and age_days(path) > compress_age_days:
            size_before = os.path.getsize(path)
            if size_before == 0:
                continue
            saved = gzip_file(path, dry_run)
            result["compressed"] += 1
            result["bytes_freed"] += saved

    # Clean up 0-byte .log files whose .gz counterparts exist and are valid
    if not dry_run:
        for entry in os.listdir(logs_path):
            path = os.path.join(logs_path, entry)
            if entry.endswith(".log") and os.path.isfile(path) and os.path.getsize(path) == 0:
                gz_path = path + ".gz"
                if os.path.exists(gz_path) and os.path.getsize(gz_path) > 100:
                    try:
                        os.remove(path)
                    except Exception:
                        pass

    return result


def clean_cron_output(cron_output_path, compress_age_days, dry_run):
    result = {"action": "cron_output", "tier": 1, "compressed": 0,
              "bytes_freed": 0, "errors": []}
    if not os.path.isdir(cron_output_path):
        return result

    for dp, _, filenames in os.walk(cron_output_path):
        for f in filenames:
            if f.endswith(".gz"):
                continue
            path = os.path.join(dp, f)
            if not os.path.isfile(path):
                continue
            if age_days(path) > compress_age_days:
                size_before = os.path.getsize(path)
                saved = gzip_file(path, dry_run)
                result["compressed"] += 1
                result["bytes_freed"] += saved

    return result


# ── Tier 2: Low Risk ───────────────────────────────────────────────────────

def clean_session_jsons(sessions_path, compress_age_days, dry_run):
    result = {"action": "session_jsons", "tier": 2, "compressed": 0,
              "bytes_freed": 0, "errors": []}
    if not os.path.isdir(sessions_path):
        return result

    for entry in os.listdir(sessions_path):
        if not entry.endswith(".json"):
            continue
        path = os.path.join(sessions_path, entry)
        if not os.path.isfile(path):
            continue
        if age_days(path) > compress_age_days:
            size_before = os.path.getsize(path)
            saved = gzip_file(path, dry_run)
            result["compressed"] += 1
            result["bytes_freed"] += saved
            if not dry_run:
                gz_path = path + ".gz"
                if not os.path.exists(gz_path):
                    result["errors"].append(f"gzip failed for {path}")
                    result["compressed"] -= 1
                    result["bytes_freed"] -= saved

    return result


# ── Tier 3: Analysis Only ──────────────────────────────────────────────────

def analyze_state_db(db_path):
    result = {"action": "state_db_analysis", "tier": 3, "exists": False,
              "size": 0, "tables": []}
    if not os.path.isfile(db_path):
        return result

    result["exists"] = True
    result["size"] = os.path.getsize(db_path)

    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type='table'")
        for (table_name,) in c.fetchall():
            if table_name.startswith("sqlite_"):
                continue
            try:
                c.execute(f'SELECT COUNT(*) FROM "{table_name}"')
                count = c.fetchone()[0]
                result["tables"].append({"name": table_name, "rows": count})
            except Exception:
                pass
        wal_path = db_path + "-wal"
        if os.path.exists(wal_path):
            result["wal_size"] = os.path.getsize(wal_path)
        conn.close()
    except Exception as e:
        result["error"] = str(e)

    return result


def analyze_commons(commons_path):
    result = {"action": "commons_analysis", "tier": 3, "data_size": 0,
              "db_size": 0, "data_files": [], "db_files": []}
    if not os.path.isdir(commons_path):
        return result

    for sub in ("data", "db"):
        sub_path = os.path.join(commons_path, sub)
        if not os.path.isdir(sub_path):
            continue
        for entry in os.listdir(sub_path):
            fp = os.path.join(sub_path, entry)
            if not os.path.isfile(fp):
                continue
            info = {"name": entry, "size": os.path.getsize(fp),
                    "age_days": round(age_days(fp), 1)}
            if sub == "data":
                result["data_size"] += info["size"]
                result["data_files"].append(info)
            else:
                result["db_size"] += info["size"]
                result["db_files"].append(info)

    return result


# ── Assess ─────────────────────────────────────────────────────────────────

def assess(cfg):
    lines = []
    total, used, free, pct = disk_usage()
    lines.append(f"Disk: {fmt(used)} / {fmt(total)} ({pct:.0f}% used, {fmt(free)} free)")

    if pct < 50:
        lines.append("Status: OK — disk usage below 50%, no cleanup needed.")
        return lines

    lines.append(f"Status: Disk at {pct:.0f}% — cleanup recommended.")
    lines.append("")

    # Snapshots
    sp = cfg["snapshots_path"]
    if os.path.isdir(sp):
        snap_dirs = [d for d in os.listdir(sp) if os.path.isdir(os.path.join(sp, d))]
        snap_size = du(sp)
        old_snaps = []
        for d in snap_dirs:
            dp = os.path.join(sp, d)
            oldest = oldest_mtime_in_dir(dp)
            age = (datetime.datetime.now().timestamp() - oldest) / 86400
            if age > cfg["snapshot_max_age_days"]:
                old_snaps.append(d)
        old_size = sum(du(os.path.join(sp, d)) for d in old_snaps)
        lines.append(
            f"Snapshots: {len(snap_dirs)} dirs, {fmt(snap_size)} total, "
            f"{len(old_snaps)} older than {cfg['snapshot_max_age_days']}d "
            f"({fmt(old_size)} reclaimable)")

    # Logs
    lp = cfg["logs_path"]
    if os.path.isdir(lp):
        log_size = du(lp)
        old_logs = sum(1 for f in os.listdir(lp)
                       if f.endswith(".log") and os.path.isfile(os.path.join(lp, f))
                       and age_days(os.path.join(lp, f)) > cfg["log_compress_age_days"])
        old_gz = sum(1 for f in os.listdir(lp)
                     if f.endswith(".gz") and os.path.isfile(os.path.join(lp, f))
                     and age_days(os.path.join(lp, f)) > cfg["log_delete_age_days"])
        lines.append(f"Logs: {fmt(log_size)} total, {old_logs} to compress, {old_gz} .gz to delete")

    # Cron output
    cp = cfg["cron_output_path"]
    if os.path.isdir(cp):
        cron_size = du(cp)
        old_cron = sum(1 for dp, _, fs in os.walk(cp) for f in fs
                       if not f.endswith(".gz")
                       and os.path.isfile(os.path.join(dp, f))
                       and age_days(os.path.join(dp, f)) > cfg["cron_output_compress_age_days"])
        lines.append(f"Cron output: {fmt(cron_size)} total, {old_cron} files to compress")

    # Session JSONs
    sesp = cfg["sessions_path"]
    if os.path.isdir(sesp):
        json_files = [f for f in os.listdir(sesp) if f.endswith(".json")]
        gz_files = [f for f in os.listdir(sesp) if f.endswith(".gz")]
        json_size = sum(os.path.getsize(os.path.join(sesp, f)) for f in json_files)
        old_json = sum(1 for f in json_files
                       if age_days(os.path.join(sesp, f)) > cfg["session_compress_age_days"])
        lines.append(
            f"Session JSONs: {len(json_files)} .json + {len(gz_files)} .gz, "
            f"{fmt(json_size)} total, {old_json} older than "
            f"{cfg['session_compress_age_days']}d compressible")

    # State DB
    dbp = cfg["state_db_path"]
    if os.path.isfile(dbp):
        db_size = os.path.getsize(dbp)
        wal_size = os.path.getsize(dbp + "-wal") if os.path.exists(dbp + "-wal") else 0
        lines.append(f"State DB: {fmt(db_size)} (+ {fmt(wal_size)} WAL)")

    return lines


# ── Clean ──────────────────────────────────────────────────────────────────

def clean(cfg):
    tier_limit = int(cfg.get("tier_limit", 3))
    results = []

    results.append(clean_snapshots(cfg["snapshots_path"], cfg["snapshot_max_age_days"], cfg["dry_run"]))
    results.append(clean_logs(cfg["logs_path"], cfg["log_compress_age_days"],
                              cfg["log_delete_age_days"], cfg["dry_run"]))
    results.append(clean_cron_output(cfg["cron_output_path"],
                                     cfg["cron_output_compress_age_days"], cfg["dry_run"]))

    if tier_limit >= 2:
        results.append(clean_session_jsons(cfg["sessions_path"],
                                           cfg["session_compress_age_days"], cfg["dry_run"]))

    return results


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Genie — VPS Disk Guardian")
    parser.add_argument("--assess", action="store_true", help="Assess disk usage and cleanup targets")
    parser.add_argument("--clean", action="store_true", help="Execute cleanup")
    parser.add_argument("--dry-run", action="store_true", help="Preview without deleting")
    parser.add_argument("--tier", type=int, choices=[1, 2, 3], default=3,
                        help="Max tier to run (1=safe, 2=+sessions, 3=+analysis)")
    parser.add_argument("--analyze", action="store_true", help="Run Tier 3 analysis (read-only)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    cfg = dict(DEFAULTS)
    cfg["tier_limit"] = str(args.tier)
    if args.dry_run:
        cfg["dry_run"] = True
    if not args.assess and not args.clean and not args.analyze:
        args.assess = True

    output = []

    if args.assess:
        output.extend(assess(cfg))

    if args.clean:
        if not output:
            output.extend(assess(cfg))
        output.append("")
        output.append("── Cleanup Results ──")
        results = clean(cfg)
        total_freed = 0
        for r in results:
            freed = r.get("bytes_freed", 0)
            total_freed += freed
            output.append(f"  [T{r.get('tier','?')}] {r['action']}: freed {fmt(freed)}")
            if r.get("errors"):
                for err in r["errors"]:
                    output.append(f"    ERROR: {err}")
        output.append(f"  Total freed: {fmt(total_freed)}")
        total, used, free, pct = disk_usage()
        output.append(f"  Disk after: {fmt(used)} / {fmt(total)} ({pct:.0f}% used)")

    if args.analyze:
        if not output:
            output.extend(assess(cfg))
        output.append("")
        output.append("── Tier 3 Analysis ──")
        db_result = analyze_state_db(cfg["state_db_path"])
        if db_result["exists"]:
            output.append(f"  state.db: {fmt(db_result['size'])}")
            for t in db_result["tables"]:
                output.append(f"    {t['name']}: {t['rows']:,} rows")
            if "wal_size" in db_result:
                output.append(f"    WAL: {fmt(db_result['wal_size'])}")
        else:
            output.append("  state.db: not found")
        commons_result = analyze_commons(cfg["commons_path"])
        if commons_result["data_files"] or commons_result["db_files"]:
            output.append(f"  commons/data: {fmt(commons_result['data_size'])}, "
                          f"{len(commons_result['data_files'])} files (oldest: "
                          f"{max(f['age_days'] for f in commons_result['data_files']):.0f}d)")
            output.append(f"  commons/db: {fmt(commons_result['db_size'])}, "
                          f"{len(commons_result['db_files'])} files (oldest: "
                          f"{max(f['age_days'] for f in commons_result['db_files']):.0f}d)")

    if args.json:
        print(json.dumps({"lines": output, "config": {k: str(v) for k, v in cfg.items()}}))
    else:
        print("\n".join(output))


if __name__ == "__main__":
    main()
