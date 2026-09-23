#!/usr/bin/env python3
"""Regression tests: retention must never destroy a live backup.
History: historical_backup_candidates() added every entry in a backup root, so
the current database copies the backup pipeline refreshes in place were treated
as redundant history — retention kept one and deleted the rest on every
--clean.
An adversarial audit of that fix found three more holes it had introduced:
scoping the protection to FILES left every undated live DIRECTORY an
unconditional candidate; symlinks were followed, so `latest -> 2026-08-16`
counted twice and retention kept the link while deleting the real directory;
and matching "any eight digits" as a date stripped protection from account
numbers, phone numbers and epoch stamps. Finally, if every candidate was
classed invalid the keep-list came out empty and the whole set was reclaimed.
2026-09-22: the candidate walk also read two HARDCODED trees — $HERMES_HOME's
migrations/ and profiles/ — whatever cfg it was handed, so it could neither be
scoped nor tested; the first *.bak-* file written under profiles/ leaked into
every fixture here. Scoping it exposed the real defect underneath: retention
bucketed by "kind", and db-bak/migration-backup are one kind across unrelated
directories, so the newest *.bak-* anywhere under profiles/ reclaimed every
other skill's only copy.
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
EMPTY = None  # scan root with nothing in it; set in main()
def check(label, condition, detail=""):
    print("%-48s %s %s" % (label, "PASS" if condition else "FAIL", detail))
    if not condition:
        FAILURES.append(label)
def touch(path, text="x", mtime=None):
    with open(path, "w") as fh:
        fh.write(text)
    if mtime is not None:
        os.utime(path, (mtime, mtime))
def cfg_for(backup_paths, **extra):
    """A config scoped to the fixture tree.

    The candidate walk covers four roots, not two: the backup paths, the
    snapshot path, the migrations tree and the profiles tree. Every one of them
    must be pinned at the fixtures or the suite reads the live box and asserts
    against whatever happens to be on disk.
    """
    cfg = {"backup_paths": list(backup_paths), "snapshots_path": None,
           "migrations_path": EMPTY, "profiles_path": EMPTY}
    cfg.update(extra)
    return cfg
def candidates(backups):
    return {os.path.basename(c["path"])
            for c in genie.historical_backup_candidates(cfg_for([backups]))}
def main():
    global EMPTY
    root = tempfile.mkdtemp(prefix="genie-retention-")
    try:
        EMPTY = os.path.join(root, "empty")
        os.makedirs(EMPTY)
        backups = os.path.join(root, "backups")
        os.makedirs(backups)
        # live copy set — refreshed in place by the backup pipeline
        live_files = ["chronicle.db", "weave.sqlite", "styx.db", "transactions.db",
                      "state.db"]
        for name in live_files:
            touch(os.path.join(backups, name), "live copy")
        # names that merely contain digits are NOT dates
        fake_dates = ["contacts-15551234567.vcf", "stripe-acct-10024537.json",
                      "invoice-90210347.pdf", "chronicle.db.1755300000"]
        for name in fake_dates:
            touch(os.path.join(backups, name), "live export")
        # an undated live DIRECTORY the pipeline rewrites in place
        current = os.path.join(backups, "current")
        os.makedirs(current)
        touch(os.path.join(current, "chronicle.db"), "live")
        # genuinely historical artifacts
        dated_dir = os.path.join(backups, "active-dbs-20260714")
        os.makedirs(dated_dir)
        touch(os.path.join(dated_dir, "chronicle.db"), "old")
        for name in ["snapshot-2026-07-01.tar.gz", "chronicle.db.bak-20260712"]:
            touch(os.path.join(backups, name), "historical")
        # a symlink pointing at a real backup directory
        os.symlink(dated_dir, os.path.join(backups, "latest"))
        found = candidates(backups)
        for name in live_files:
            check("live copy protected: %s" % name, name not in found)
        for name in fake_dates:
            check("digits are not a date: %s" % name, name not in found)
        check("undated live directory protected: current/", "current" not in found)
        check("symlink never a candidate: latest", "latest" not in found)
        check("dated dir is a candidate", "active-dbs-20260714" in found)
        check("dated archive is a candidate", "snapshot-2026-07-01.tar.gz" in found)
        check("dated .bak file is a candidate", "chronicle.db.bak-20260712" in found)
        check("candidate count is exactly 3", len(found) == 3, sorted(found))
        # the walk covers only the roots it was given: a *.bak-* file outside
        # them is not this config's business
        stray = os.path.join(root, "unscanned")
        os.makedirs(stray)
        touch(os.path.join(stray, "outside.db.bak-20260901"), "stray")
        check("scan roots are cfg-driven", len(candidates(backups)) == 3,
              sorted(candidates(backups)))
        # retention never empties the keep-list, even when every candidate is
        # classed invalid (here: every dated dir holds a full state.db copy)
        root2 = os.path.join(root, "b2")
        os.makedirs(root2)
        for day in ("20260801", "20260802"):
            d = os.path.join(root2, "full-%s" % day)
            os.makedirs(d)
            touch(os.path.join(d, "state.db"), "state")
        plan = genie.backup_retention_plan(cfg_for(
            [root2], allow_local_state_db_backup=False,
            historical_backup_keep_count=1))
        check("all-invalid: keeps one anyway", len(plan["keep"]) == 1,
              [os.path.basename(k["path"]) for k in plan["keep"]])
        check("all-invalid: keeps the NEWEST",
              os.path.basename(plan["keep"][0]["path"]) == "full-20260802",
              [os.path.basename(k["path"]) for k in plan["keep"]])
        check("all-invalid: reclaims the rest", len(plan["reclaim"]) == 1)
        # recency decides: a newer PARTIAL backup must never cause today's copy
        # to be deleted in favour of a much older complete one
        root3 = os.path.join(root, "b3")
        os.makedirs(root3)
        old_complete = os.path.join(root3, "full-20250101")
        os.makedirs(old_complete)
        for name in ("chronicle.db", "weave.sqlite", "styx.db"):
            touch(os.path.join(old_complete, name), "old")
        new_partial = os.path.join(root3, "full-20260816")
        os.makedirs(new_partial)
        touch(os.path.join(new_partial, "chronicle.db"), "today")
        os.utime(old_complete, (1735689600, 1735689600))
        plan3 = genie.backup_retention_plan(
            cfg_for([root3], historical_backup_keep_count=1))
        kept = {os.path.basename(k["path"]) for k in plan3["keep"]}
        check("today's backup is never reclaimed", "full-20260816" in kept, sorted(kept))
        check("the complete older backup is also kept", "full-20250101" in kept, sorted(kept))
        # retention is per class/root, so separate roots cannot delete each
        # other's only copy
        r_a = os.path.join(root, "rootA")
        r_b = os.path.join(root, "rootB")
        for base in (r_a, r_b):
            os.makedirs(base)
            for day in ("20260810", "20260815"):
                d = os.path.join(base, "dump-%s" % day)
                os.makedirs(d)
                touch(os.path.join(d, "chronicle.db"), "x")
        plan4 = genie.backup_retention_plan(
            cfg_for([r_a, r_b], historical_backup_keep_count=1))
        kept_roots = {os.path.dirname(k["path"]) for k in plan4["keep"]}
        check("each backup root keeps its own", kept_roots == {r_a, r_b},
              sorted(os.path.basename(x) for x in kept_roots))
        # the same rule governs out-of-band copies: two unrelated skills each
        # holding their ONLY *.bak-* must not compete for one retention slot
        prof = os.path.join(root, "profiles-tree")
        data = os.path.join(prof, "indigo", "commons", "data")
        for skill, name, mtime in (("skill-a", "alpha.json.bak-20260801", 1785000000),
                                   ("skill-b", "beta.json.bak-20260802", 1786000000)):
            d = os.path.join(data, skill)
            os.makedirs(d)
            touch(os.path.join(d, name), "only copy", mtime)
        plan5 = genie.backup_retention_plan(cfg_for(
            [], profiles_path=prof, historical_backup_keep_count=1))
        check("unrelated .bak- dirs keep their own",
              not plan5["reclaim"],
              [os.path.basename(r["path"]) for r in plan5["reclaim"]])
        # ...while two copies of one file in one directory ARE history
        touch(os.path.join(data, "skill-a", "alpha.json.bak-20260803"),
              "newer", 1787000000)
        plan6 = genie.backup_retention_plan(cfg_for(
            [], profiles_path=prof, historical_backup_keep_count=1))
        check("same-directory .bak- history is thinned",
              [os.path.basename(r["path"]) for r in plan6["reclaim"]]
              == ["alpha.json.bak-20260801"],
              [os.path.basename(r["path"]) for r in plan6["reclaim"]])
        # migration backups are bucketed by their own directory too
        mig = os.path.join(root, "migrations")
        for job, mtime in (("peopledb", 1785500000), ("takeout-2026-06-28", 1786500000)):
            d = os.path.join(mig, job, "backups")
            os.makedirs(d)
            touch(os.path.join(d, "pre-migration.db"), "only copy", mtime)
        plan7 = genie.backup_retention_plan(cfg_for(
            [], migrations_path=mig, historical_backup_keep_count=1))
        check("unrelated migration backups keep their own",
              not plan7["reclaim"],
              [os.path.basename(r["path"]) for r in plan7["reclaim"]])
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
