---
name: genie
description: VPS disk cleanup. Deletes old snaps, logs, and cron files. Not for database maintenance, log rotation configuration, or real-time monitoring.
version: 1.7.0
author: Indigo Karasu (indigokarasu)
license: MIT
platforms: [linux]
source: https://github.com/indigokarasu/genie
includes:
  - references/**
  - scripts/**
metadata:
  hermes:
    tags: [cleanup, disk-space, filesystem, maintenance]
    category: infrastructure
    config:
      - key: genie.snapshot_max_age_days
        description: "Delete snapshots older than N days"
        default: "7"
      - key: genie.log_compress_age_days
        description: "Compress logs older than N days"
        default: "7"
      - key: genie.log_delete_age_days
        description: "Delete compressed logs older than N days"
        default: "30"
      - key: genie.cron_output_compress_age_days
        description: "Compress cron output files older than N days"
        default: "7"
      - key: genie.session_compress_age_days
        description: "Compress session JSONs older than N days"
        default: "14"
      - key: genie.tmp_stale_hours
        description: "Delete /tmp files older than N hours (0 to skip)"
        default: "24"
      - key: genie.git_clone_max_age_days
        description: "Delete git clones in /root/projects/ untouched for N days (must have remote)"
        default: "5"
      - key: genie.dry_run
        description: "If true, only report — don't delete/compress"
        default: "false"
---

# Genie — VPS Disk Cleanup

Safely reclaims disk space on Linux VPS and workstations by deleting or compressing stale state snapshots, logs, cron output, temp files, and package caches. Does not touch live databases, auth files, or active sessions.

## When to Use

- VPS disk usage is high (above 50%)
- User asks to "clean up disk space" or "check disk usage"
- Weekly maintenance cron fires
- Before/after large operations (backups, migrations)

## When NOT to Use

- Database maintenance tasks (genie does not manage databases)
- Real-time monitoring or alerting
- Log rotation configuration (genie handles specific files, not system-wide logrotate)

## Prerequisites

No external dependencies — uses only Python 3.11+ stdlib.

Optional: set `GENIE_*` environment variables to override defaults (see Configuration below).

## How to Run

```bash
# Assess disk usage and identify cleanup targets
python3 /root/.hermes/profiles/indigo/skills/ocas-genie/scripts/genie.py --assess

# Execute cleanup (Tier 1 + Tier 2)
python3 /root/.hermes/profiles/indigo/skills/ocas-genie/scripts/genie.py --clean

# Dry run — preview without deleting
python3 /root/.hermes/profiles/indigo/skills/ocas-genie/scripts/genie.py --clean --dry-run

# Map filesystem and generate FILESYSTEM.md manifest
python3 /root/.hermes/profiles/indigo/skills/ocas-genie/scripts/genie.py --discover
```

For large file counts (>2,000), run in background: `terminal(background=True, notify_on_complete=True)`.

## Quick Reference

| Flag | Action |
|------|--------|
| `--assess` | Report disk usage and cleanup targets |
| `--clean` | Execute Tier 1 + Tier 2 cleanup |
| `--clean --tier 1` | Only Tier 1 (zero risk) |
| `--dry-run` | Preview without modifying anything |
| `--discover` | Map filesystem, create/update FILESYSTEM.md |
| `--analyze` | Tier 3 analysis only (read-only) |
| `--json` | Output as JSON |

## Procedure

1. **Locate the script** — check these paths in order:
   - `/root/.hermes/profiles/indigo/skills/ocas-genie/scripts/genie.py` (profile — note `ocas-` prefix)
   - `/root/.hermes/profiles/indigo/scripts/genie.py` (profile scripts dir — alternate location)
   - `/root/.hermes/skills/ocas-genie/scripts/genie.py` (skill-bundled)
   - Use absolute paths only — never `~` in cron context
   - **Gotcha**: the skill folder is `ocas-genie/`, not `genie/`. A literal read of the old path will fail with ENOENT.

2. **Assess** — run `--assess` to identify targets

3. **Execute** — run `--clean` (or `--clean --dry-run` to preview)

4. **Report** — verify with `df -h /` after cleanup

## Manual Targets (outside genie's scope)

Some large disk consumers are NOT cleaned by genie's `--clean` because they require user judgment:

1. **Pre-update snapshots** (`/root/.hermes/state-snapshots/`) — can be 10+ GB each. Safe to delete old ones once the post-update gateway is confirmed healthy. See `references/disk-growth-patterns.md`.
2. **Migration backups** (`/root/.hermes/migrations/*/backups/`) — large DB copies from completed migrations (6+ GB observed). Safe to delete once the migration's CHECKPOINT.md confirms completion. See `references/disk-growth-patterns.md`.
3. **Pre-migration `.bak-*` files** (`profiles/*/commons/db/*/.bak-*`) — migration scripts leave full DB backups next to live DBs. Safe to delete once the live DB has writes newer than the backup timestamp. See `references/disk-growth-patterns.md`.
4. **Manual backups** (`/root/backup/`) — user-created, may be the only restore point. Always ask before deleting.
5. **Browser caches** (`~/.cache/camoufox/`) — safe to delete but not tracked by genie. Add to `--clean` output as a suggestion.
6. **Stale /tmp extracts** (`/tmp/camoufox-*/`, `/tmp/uc_*/`, `/tmp/body_*`) — tool engine extracts and debug bodies that persist beyond genie's 24h /tmp cleanup. Safe to delete when the creating process is not running.
7. **Inactive git clones** (`/root/projects/`) — Tier 1 auto-cleaned by genie. Only deletes dirs with a confirmed remote (`url =` in `.git/config`) and no working-tree changes in >5 days. Local-only repos (no remote) are never touched.
8. **Git clones in `/root/projects/`** — often 10+ GB total, all re-clonable from GitHub. Not tracked by genie. Safe to remove when not actively worked on.
9. **state.db VACUUM** — genie does not run `VACUUM` or `incremental_vacuum` on state.db. If the DB has high freelist pages, reclaim manually: `sqlite3 state.db "PRAGMA incremental_vacuum(1000);"` (safer for large DBs than full VACUUM).

When disk is critically high, flag these in your report even though genie can't auto-clean them.

## Safety Rules

- NEVER modify `state.db` directly — Tier 3 analysis only. Note: `/root/.hermes/state.db` is typically a symlink to a profile's DB (e.g., `→ profiles/indigo/state.db`). Resolve symlinks before analyzing or reporting.
- NEVER delete files without compressing first (Tier 2+)
- ALWAYS report what was done
- If disk usage is below 50%, report "no action needed"
- If any operation fails, report the error and continue
- If a snapshot deletion fails, leave the snapshot in place and report at the end
- The most recent snapshot is always preserved (never auto-deleted)
- **Do not suggest deleting backups, state.db, or state-snapshots** — the user keeps exactly 1 backup + current live DB. Count but do not propose removal.

## Error Handling

- **gzip failures:** If `gzip -t` reports a `.gz` is corrupt but the original exists, keep the original and regenerate. Never delete the original while the gzip is corrupt.
- **Concurrent gzip race:** Only one gzip per file. A timed-out foreground command can leave a background shell that spawns a second gzip. Verify with `gzip -t`, then remove the original.
- **Disk-at-100%:** Focus on immediate space recovery (Tier 1 cleanup) before any backup workflow.
- **Snapshot deletion failure:** Leave the snapshot in place, report the error, continue to next target.

## What Genie Cleans

### Tier 1 — Zero Risk (auto-executed)
1. **Stale state snapshots** — directories older than 7 days (most recent always preserved)
2. **Old log files** — compress after 7 days, delete compressed after 30 days
3. **Old cron output** — compress after 7 days
4. **Stale `/tmp` files** — delete after 24 hours
5. **Package caches** — pip, uv, npm (all rebuildable)
6. **Browser profile caches** — `~/.cache/camoufox/` (rebuildable, often 1+ GB)
7. **Inactive git clones** — `/root/projects/` dirs untouched >5 days with confirmed remote (safe to re-clone)

### Tier 2 — Low Risk (requires confirmation)
1. **Session JSON duplicates** — compress after 14 days (data also in `state.db`)

### Tier 3 — Analysis Only (never auto-executes)
1. **state.db bloat analysis** — reports DB size, freelist waste
2. **Large directories** — reports git checkpoints, commons/data, commons/db for manual review

## Configuration

| Variable | Default | Description |
|---|---|---|
| `GENIE_SNAPSHOT_MAX_AGE_DAYS` | 7 | Delete snapshots older than N days |
| `GENIE_LOG_COMPRESS_AGE_DAYS` | 7 | Compress logs older than N days |
| `GENIE_LOG_DELETE_AGE_DAYS` | 30 | Delete compressed logs older than N days |
| `GENIE_CRON_OUTPUT_COMPRESS_AGE_DAYS` | 7 | Compress cron output older than N days |
| `GENIE_SESSION_COMPRESS_AGE_DAYS` | 14 | Compress session JSONs older than N days |
| `GENIE_TMP_STALE_HOURS` | 24 | Delete /tmp files older than N hours (0 to skip) |
| `GENIE_DRY_RUN` | false | If true, only report — don't delete/compress |

## Verification

- `df -h /` — check disk usage dropped
- `du -sh /root/.hermes/` — check .hermes size
- Session search still works (confirms state.db intact)

## Support File Map

| File | When to read |
|---|---|
| `references/genie-gotchas.md` | Before first production run or when debugging |
| `references/operational-notes.md` | Real-world examples and case studies |
| `references/os-walk-pitfall.md` | Debugging nested directory traversal issues |
| `references/session-2026-05-29-disk-recovery.md` | Disk emergency case study |
| `references/snapshot-backup-redaction.md` | Backing up snapshots to git/LFS |
| `references/snapshot-structures.md` | Snapshot format breakdown |
| `references/state-db-compaction.md` | Tackling state.db bloat |
| `references/state-db-size-breakdown.md` | State DB composition analysis |
| `references/disk-growth-patterns.md` | Recurring disk hogs: pre-update snapshots, /root/backup/, browser caches |
| `references/state-db-retention.md` | State DB retention policy: audit all instances, keep current + one backup, delete oldest first |
| `references/self-update-genie.md` | Self-update hash comparison procedure |
| `references/repo-path-conventions.md` | Repo path convention — all remote clones under `projects/github*` |
| `scripts/genie.py` | Main cleanup script |
| `scripts/genie_rebuild_fts.py` | FTS rebuild after restoring no-FTS backup |
