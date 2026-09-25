---
name: ocas-genie
description: Safely audits and reclaims VPS/Linux disk space, investigates root-filesystem growth, and enforces backup retention when disk usage is high or maintenance is requested; use keywords disk cleanup, disk full, disk usage, snapshots, backups, stale repos, or disk spike. NOT for database maintenance beyond read-only analysis, logrotate configuration, or real-time monitoring.
license: MIT
version: "1.9.1"
author: Indigo Karasu (indigokarasu)
source: https://github.com/indigokarasu/genie
triggers:
  - disk cleanup
  - disk full
  - disk usage
  - disk spike
  - snapshots
  - backup retention
  - stale repos
includes:
  - references/**
  - scripts/**
metadata:
  hermes:
    tags: [cleanup, disk-space, filesystem, maintenance]
    category: infrastructure
    platforms: [linux]
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
        description: "Delete clones under <projects-root>/ untouched for N days (remote required)"
        default: "5"
      - key: genie.dry_run
        description: "If true, only report — don't delete/compress"
        default: "false"
---

# Genie — VPS Disk Cleanup

Safely reclaims disk space on Linux VPS and workstations by deleting or compressing stale state snapshots, logs, cron output, temp files, and package caches. Also owns `/root` disk-spike investigation, duplicate-repo detection, and backup-retention audits. Does not touch live databases, auth files, or active sessions.

## When to Use

- Disk usage is high (above 50%) or a disk-space alert fires
- User asks to "clean up disk space", "check disk usage", or why usage grew
- `/root` needs a safe audit/classification pass
- Backup dirs, snapshots, or `.bak-*` files may violate the retention rule
- Weekly maintenance cron fires, or a large operation is due

## When NOT to Use

- Database maintenance beyond read-only analysis — genie never repairs or VACUUMs a DB
- Real-time monitoring or alerting
- System-wide logrotate configuration (genie compresses specific known files only)

## Prerequisites

Python 3.11+ stdlib only — no dependencies. Settings live in `config.yaml` under `skills.config.genie.*`; behavioral settings are never read from environment variables.

## How to Run

```bash
SCRIPT=<hermes-home>/profiles/indigo/skills/ocas-genie/scripts/genie.py
python3 "$SCRIPT" --assess          # report targets (read-only)
python3 "$SCRIPT" --clean           # Tier 1 + Tier 2 cleanup
python3 "$SCRIPT" --clean --dry-run # preview, no changes
python3 "$SCRIPT" --discover        # map filesystem → FILESYSTEM.md
```

For large file counts (>2,000) run in background: `terminal(background=True, notify_on_complete=True)`.

## Quick Reference

| Flag | Action |
|------|--------|
| `--assess` | Report disk usage and cleanup targets |
| `--clean` | Execute Tier 1 + Tier 2 cleanup |
| `--clean --tier 1` | Only Tier 1 (zero risk) |
| `--dry-run` | Preview without modifying anything |
| `--discover` | Map the filesystem into FILESYSTEM.md |
| `--analyze` | Tier 3 analysis only (read-only) |
| `--json` | Output as JSON |

**Example** — `--assess` output shape:

```text
Backup freshness: STALE — backup_all 41h  (backup-class cleanup will be refused)
State DB: 14.6 GB (+ 531 KB WAL) → live data 14.5 GB, free-list bloat 80 MB (0.5%)
```

## Backup Retention Rule

Keep **one historical backup**, plus current live data — genie detects violations. Classes: `<fs-root>/backup/*`, `<fs-root>/backups/*`, profile `state-snapshots/*`, `<hermes-home>/migrations/*/backups/*`, and profile DB `.bak-*` copies. Keep the newest valid backup; older or invalid copies are reclaimable (local full `state.db` copies are invalid unless explicitly requested). Remove the superseded backup only after the replacement verifies. Full workflow: `references/root-audit-and-backup-retention.md`.

## Procedure

Assessment precedes destructive cleanup; independent verification follows. Why: an aggregate total cannot prove which backup survived, and a nearly-full disk can make a later verification command fail.

- [ ] Locate the live script (`profiles/indigo/skills/ocas-genie/scripts/genie.py`, then `profiles/indigo/scripts/genie.py`, then `<hermes-home>/skills/ocas-genie/scripts/genie.py`); absolute paths only — never `~` in cron. Gotcha: the folder is `ocas-genie/`, not `genie/` — the literal old path fails with ENOENT.
- [ ] Capture the `--assess` (or `--clean --dry-run`) report before changing files.
- [ ] Confirm the newest snapshot/backup is protected and no backup class is stale.
- [ ] Run the smallest authorized cleanup tier.
- [ ] Verify `df`, snapshot survival, and live-DB integrity (see Verification), then report.

## Safety Rules

- NEVER modify `state.db` directly — Tier 3 analysis only. `<hermes-home>/state.db` is usually a symlink to a profile DB; resolve with `readlink -f`, size with `stat -L` (the symlink itself is ~38 B).
- One-historical-backup rule: current live data plus the newest valid historical backup; older copies/snapshots are reclaimable.
- NEVER delete without compressing first (Tier 2+) unless removing a superseded historical backup under the one-backup rule.
- ALWAYS report what was done; below 50% usage report "no action needed"; on any failure report the error and continue.
- If a snapshot deletion fails, leave the snapshot in place and report it at the end.
- **Snapshot preservation is currently UNDERMINED** — `backup_retention` can delete the most-recent snapshot today (Known Issues). Verify the snapshot dir after every `--clean`; never trust the summary line.
- **Repo deletion guard (v1.8.0, enforced in code — `clone_delete_blockers()`):** deletable only when the tree is clean, has no stashes, every local branch is fully pushed to a configured upstream, has a remote, is untouched > `git_clone_max_age_days`, and is not in `git_clones_protected`. Why: the gate once existed only on paper, and the gap destroyed a production clone. It fails closed, contacts the remote, scrubs `GIT_DIR`/`GIT_WORK_TREE`, and blocks on git-ignored non-rebuildable paths, tag-only commits, submodules, and linked worktrees. Gate details: `references/clone-deletion-safety.md`; deletion playbook: `references/manual-repo-pruning.md`.
- **Backup-freshness gate (v1.8.0):** while `backup_stamps_path` exists and any `<name>.ok` stamp is older than `backup_stamp_max_age_hours` (default 26), backup-class cleanup is refused. Why: the moment the offsite pipeline stops, the local copy is the only copy. `--assess` prints a `Backup freshness:` line; no stamp dir = inactive.
- **Do not preserve multiple backups:** count all historical classes together and remove older valid copies.

## Known Issues / Pitfalls

- **`backup_retention` can delete the most-recent rollback snapshot (CONFIRMED BUG).** It keeps the single newest candidate across ALL backup classes; `snapshots: freed 0.0 B` is NOT proof. Analysis: `references/genie-snapshot-retention-bug.md`.
- **No per-file deletion manifest** — `--clean` prints aggregate totals only; capture pre-clean listings for an audit trail.
- **Wrong snapshot path in older docs** — snapshots live in the profile dir (`profiles/<profile>/state-snapshots`), not the bare `<hermes-home>/state-snapshots`.
- **Decoy-script trap + unreachable prune (root cause of `<fs-root>/backup` bloat).** The live writer is `backup_all_hermes_data.sh`, not `backup_system.sh`; its prune sat after the 14G `state.db` copy under `set -e`, so ENOSPC aborts skipped it. Fix applied 2026-07-14 — run `references/backup-prune-diskfull-trap.md`'s recipe before re-patching.
- **Silent no-ops, and publishing.** A retention line on a nonexistent path fails quietly under `>/dev/null`; unpushed edits in the live skill repo can be clobbered by `skill-sync-all`. See `references/maintenance-lessons.md`.
- **Re-investigation discipline:** find the live writer via the real chain (`jobs.json`, cron output, wrapper `exec`s), never a plausibly-named sibling — and check the retention line is *reachable*.

## Error Handling

| Failure | Handling |
|---|---|
| `--clean` operation error | Record and report every failed target; continue independent targets. |
| Snapshot deletion fails | Leave it in place, verify the directory directly, report. |
| Disk reaches 100% | Tier 1 recovery only; defer backup workflows — copy/verify needs temp space. |
| `gzip -t` finds corruption | Keep the original, regenerate, delete nothing until the replacement passes. |
| Integrity check is not `ok` | Stop database follow-up, preserve the DB, escalate the exact result; genie never repairs DBs. |

## What Genie Cleans

**Tier 1 — zero risk (auto):** snapshots >7d (most recent preserved), logs (compress >7d, delete compressed >30d), cron output >7d, `/tmp` >24h, pip/uv/npm caches, browser caches, inactive git clones (>5d, remote confirmed).
**Tier 2 — low risk (confirmation):** session JSON duplicates — compress after 14 days (data also lives in `state.db`).
**Tier 3 — analysis only (never auto-executes):** state.db bloat analysis (default pass: `live_bytes`, `bloat_bytes`, `bloat_pct`, VACUUM verdict); large-directory report.

## Manual / Investigative Targets

Large consumers needing an audit pass — they may be live data, backups, or duplicate worktrees. Procedure: `references/root-audit-and-backup-retention.md`.

1. **Manual backups** (`<fs-root>/backup/`, `<fs-root>/backups/`) — one historical backup total; keep the newest valid.
2. **Pre-update snapshots and migration backups** — historical backups; **CAUTION:** `backup_retention` may delete snapshots (Known Issues) — verify after every `--clean`.
3. **Duplicate git repos** (same remote + same HEAD), **browser caches** (`~/.cache/camoufox/`), **stale `/tmp` extracts** — safe when no creating process runs.
4. **state.db VACUUM** — never automatic; **`bloat_pct` < ~5% → do NOT VACUUM** (mostly real data; a VACUUM needs ~`live_bytes` free on top of the original). Details: `references/state-db-vacuum-feasibility.md`.
5. **Orphaned runtimes, GPU stacks, LFS caches, duplicate model stores, aged cron transcripts** — proven-by-probe patterns in `references/disk-growth-patterns.md`.

When disk is critically high, flag these even if `--clean` cannot auto-clean them.

## Configuration

Settings live in `config.yaml` under `skills.config.genie.*`; unset keys use the frontmatter defaults, and CLI flags (e.g. `--dry-run`) override config at runtime. Safety-gate keys beyond the declared set: `git_clones_protected` ([]), `git_clones_verify_remote` (true), `backup_stamps_path` (`<hermes-home>/logs/stamps`), `backup_stamp_max_age_hours` (26), `backup_stamp_ignore` ([]), `filesystem_md` (empty), `allow_local_state_db_backup` (false). Full key table: `references/default-config-genie.md`.

## Verification

- `df -h /` and `du -sh <hermes-home>/` — confirm usage dropped.
- **Snapshot survival (MANDATORY):** `ls -la <hermes-home>/profiles/<profile>/state-snapshots/` — the most-recent pre-update snapshot MUST be present. Empty = `backup_retention` deleted it. A `freed 0.0 B` line is not proof.
- **Live DB integrity:** `sqlite3 <db> "PRAGMA integrity_check;"` → `ok` for each DB the user cares about (e.g. `styx.db`, `transactions.db` under `<hermes-home>/data/`); resolve symlinks first.
- Session search still works (confirms state.db intact).

## Support File Map

| File | When to read |
|---|---|
| `references/root-audit-and-backup-retention.md` | Disk-spike investigation; retention |
| `references/clone-deletion-safety.md` | A clone deletion is blocked or audited |
| `references/manual-repo-pruning.md` | User-requested repo deletion |
| `references/backup-prune-diskfull-trap.md` | Before touching `<fs-root>/backup` (recipe) |
| `references/genie-snapshot-retention-bug.md` | After `--clean`; missing snapshot |
| `references/genie-gotchas.md` | First run; debugging surprises |
| `references/operational-notes.md` | Real-world examples and case studies |
| `references/disk-growth-patterns.md` | Hunting recurring large consumers |
| `references/state-db-vacuum-feasibility.md` | A VACUUM decision |
| `references/state-db-compaction.md` | Compacting state.db (FTS overhead) |
| `references/state-db-size-breakdown.md` | Explaining state.db composition |
| `references/state-db-retention.md` | Auditing state.db copies |
| `references/snapshot-structures.md` | Snapshot contents vary by era |
| `references/snapshot-backup-redaction.md` | Snapshot backup to git/LFS |
| `references/repo-path-conventions.md` | A repo lives outside `projects/github*` |
| `references/os-walk-pitfall.md` | Nested traversal misbehaves |
| `references/maintenance-lessons.md` | Publishing; silent no-op retention lines |
| `references/default-config-genie.md` | Checking config keys + defaults |
| `references/genie-storage-layout.md` | Locating genie's storage files |
| `references/okrs-genie.md` | Objective-level health reporting |
| `scripts/genie.py` | The main cleanup script |
| `scripts/genie_rebuild_fts.py` | FTS rebuild after a no-FTS restore |
