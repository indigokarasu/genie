#!/usr/bin/env python3
"""Regression test: retention must never target the live backup copy set.

History: historical_backup_candidates() added every entry in a backup root,
so the current database copies the backup pipeline refreshes in place
(chronicle.db, state.db, ...) were treated as redundant historical backups —
retention kept one and deleted the rest, removing local restore points on
every --clean. Dated directories and archives ARE historical and must stay
in scope.

Run: python3 tests/test_backup_retention_scope.py
"""
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import genie  # noqa: E402

FAILURES = []


def check(label, condition, detail=""):
    print("%-42s %s %s" % (label, "PASS" if condition else "FAIL", detail))
    if not condition:
        FAILURES.append(label)


def main():
    root = tempfile.mkdtemp(prefix="genie-retention-")
    try:
        backups = os.path.join(root, "backups")
        os.makedirs(backups)

        # live copy set — refreshed in place by the backup pipeline
        live = ["chronicle.db", "weave.sqlite", "styx.db", "transactions.db", "state.db"]
        for name in live:
            with open(os.path.join(backups, name), "w") as fh:
                fh.write("live copy")

        # genuinely historical artifacts
        dated_dir = os.path.join(backups, "active-dbs-20260714")
        os.makedirs(dated_dir)
        with open(os.path.join(dated_dir, "chronicle.db"), "w") as fh:
            fh.write("old")
        for name in ["snapshot-2026-07-01.tar.gz", "chronicle.db.bak-20260712"]:
            with open(os.path.join(backups, name), "w") as fh:
                fh.write("historical")

        cfg = {"backup_paths": [backups], "snapshots_path": None}
        paths = {os.path.basename(c["path"]) for c in genie.historical_backup_candidates(cfg)}

        for name in live:
            check("live copy protected: %s" % name, name not in paths)
        check("dated dir is a candidate", "active-dbs-20260714" in paths)
        check("dated archive is a candidate", "snapshot-2026-07-01.tar.gz" in paths)
        check("dated .bak file is a candidate", "chronicle.db.bak-20260712" in paths)
        check("candidate count is exactly 3", len(paths) == 3, sorted(paths))
    finally:
        shutil.rmtree(root, ignore_errors=True)

    print()
    if FAILURES:
        print("FAILED: %s" % ", ".join(FAILURES))
        return 1
    print("ALL RETENTION SCOPE CASES PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
