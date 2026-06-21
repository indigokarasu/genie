---
name: ocas-genie
description: Hermes filesystem cleanup tool. Identifies cleanup targets across state
  snapshots, session files, logs, and cron output. Estimates space reclamation and
  executes safe deletions without reducing functionality. Use when disk usage is high,
  user asks to clean up, or weekly maintenance fires. NOT for system health monitoring
  (use ocas-custodian) or per-skill journal cleanup (use ocas-finch).
tags:
- cleanup
- disk-space
- filesystem
- maintenance
triggers:
- disk cleanup
- clean up disk
- filesystem cleanup
- storage full
- cleanup targets
license: MIT
source: https://github.com/indigokarasu/genie
includes:
- references/**
- scripts/**
metadata:
  author: Indigo Karasu (indigokarasu)
  version: 1.3.2
---

# Genie — Hermes Filesystem Cleanup

Scans the Hermes filesystem for cleanup targets — stale snapshots, old logs,
session file duplicates, and uncompressed cron output. Safely reclaims disk space
without reducing functionality. Reports what was found and what was cleaned.
Designed to run as a cron job or on-demand.

## When to Use

- VPS disk usage is high (above 50%)
- User asks to "clean up disk space" or "check disk usage"
- Weekly maintenance cron fires
- Before/after large operations (backups, migrations)

## When NOT to Use

- System health monitoring → use ocas-custodian
- Per-skill journal cleanup → use ocas-finch

## Responsibility Boundary

Genie owns VPS-level disk cleanup: state snapshots, logs, cron output, session JSONs.

Genie does not own: per-skill artifact cleanup (finch), operational failure diagnosis (custodian), or any task that modifies databases.

## What Genie Cleans (in order of safety)

### Tier 1 — Zero Risk
1. **Stale state snapshots** — Removes `state-snapshots/` directories older than N days (default: 7).
   The live `state.db` is the source of truth. Snapshots are for manual rollback only.
2. **Old log files** — Compresses logs older than 7 days, deletes compressed logs older than 30 days.
3. **Old cron output** — Compresses cron output files older than 7 days.
4. **Stale `/tmp` files** — Deletes large files in `/tmp/` that are clearly transient leftovers
   (e.g. browser `.zip` downloads, installer packages) and older than 24h. These are zero-risk:
   anything still in use won't be in `/tmp`, and `/tmp` is not persistent across reboots on most systems.
   Check `ls -la /tmp/` and look for large archives (`.zip`, `.tar.gz`, `.deb`) that were likely
   extracted or installed already. When in doubt, skip — `/tmp` cleanup yields modest gains.
5. **Package manager caches** — Safe reduction targets outside `.hermes/` that genie owns:
   - `npm cache clean --force` (clears `_npx/` and `_cacache/` under `~/.npm/`)
   - `rm -rf ~/.cache/uv/*` (uv Python package cache)
   - `rm -rf ~/.cache/pip/*` (pip cache)
   - `apt-get clean` (deb package cache)
   These are all rebuildable caches — zero functionality loss. Run `du -sh ~/.cache/ ~/.npm/`
   before and after to report impact.

### Tier 2 — Low Risk (requires confirmation)
1. **Session JSON duplicates** — Compresses session `.json` files older than 14 days.
   These contain data already in `state.db` — if a session message exists in `state.db`, its `.json` file is a safe deletion candidate. Gzip first, verify the gzip is valid, then delete the original only after confirming `state.db` has the data.
   **Confirmation required**: present the space estimate and file count to the user before executing. Proceed only after explicit approval.

### Tier 3 — Analysis Only (never auto-executes)
1. **state.db bloat analysis** — Reports on DB size, freelist waste, and largest tables.
   Does NOT modify the database — only reports.

## Configuration

| Variable | Default | Description |
|---|---|---|
| `GENIE_SNAPSHOT_MAX_AGE_DAYS` | 7 | Delete snapshots older than N days |
| `GENIE_LOG_COMPRESS_AGE_DAYS` | 7 | Compress logs older than N days |
| `GENIE_LOG_DELETE_AGE_DAYS` | 30 | Delete compressed logs older than N days |
| `GENIE_CRON_OUTPUT_COMPRESS_AGE_DAYS` | 7 | Compress cron output older than N days |
| `GENIE_SESSION_COMPRESS_AGE_DAYS` | 14 | Compress session JSONs older than N days |
| `GENIE_DRY_RUN` | false | If true, only report — don't delete/compress |
| `GENIE_STATE_DB_PATH` | `/root/.hermes/state.db` | Path to state.db |
| `GENIE_SESSIONS_PATH` | `/root/.hermes/sessions` | Path to session files |
| `GENIE_LOGS_PATH` | `/root/.hermes/logs` | Path to log files |
| `GENIE_CRON_OUTPUT_PATH` | `/root/.hermes/cron/output` | Path to cron output |
| `GENIE_SNAPSHOTS_PATH` | `/root/.hermes/state-snapshots` | Path to state snapshots |
| `GENIE_TMP_STALE_HOURS` | 24 | Delete `/tmp/` files older than N hours (0 to skip) |
| `GENIE_CACHE_PATHS` | `~/.cache/uv/*,~/.cache/pip/*` | Comma-separated glob patterns for package cache cleanup |

## Workflow

### Step 0: Locate the script
The genie script may be at any of these paths. Check all:
1. `/root/.hermes/skills/ocas-genie/scripts/genie.py` (skill-bundled)
2. `/root/.hermes/scripts/genie.py` (production copy)
3. `/root/.hermes/profiles/indigo/skills/ocas-genie/scripts/genie.py` (profile skill copy)

Use whichever exists. In production, the script is often at path 2.
**IMPORTANT:** Always use absolute paths (`/root/...`), never `~`. In cron context, `~` resolves to the profile-scoped home (`/root/.hermes/profiles/indigo/home/`), not `/root/`.

### Step 1: Assess
Get current disk usage and identify cleanup targets:
```bash
python3 <script_path> --assess
```

### Step 2: Dry Run
Run a detailed dry-run and present ALL actions. Do NOT proceed without user confirmation when file count exceeds 100.

### Step 3: Execute
For large file counts (>2,000 files), use `terminal(background=True)`:
```bash
python3 <script_path> --clean > /tmp/genie_run.log 2>&1
```

### Step 4: Report
Parse `/tmp/genie_run.log` or wait for background completion.
Always verify with `df -h /` after cleanup.

## Safety Rules

- NEVER modify `state.db` directly — always work on a copy
- NEVER run compaction (VACUUM, .backup) against the live DB — always inside a container or on a verified copy
- NEVER consider a compaction test successful until the full pipeline (copy → drop FTS → rebuild FTS → verify search) has been verified inside a container
- NEVER delete files without compressing first (for Tier 2+)
- NEVER run without verifying disk path exists
- ALWAYS report what was done
- If disk usage is below 50%, report "no action needed" and exit
- If any operation fails, report the error and continue with remaining operations. Do not halt the entire cleanup because one target failed. At the end, report all errors alongside the successes.
- If a snapshot deletion fails, leave the snapshot in place and move to the next one. Report failed deletions at the end.

## Cron Usage

Schedule: Sundays at 6 AM
```
Schedule: 0 6 * * 0
Prompt:   Run Genie: python3 /root/.hermes/scripts/genie.py. Report results.
```

**Stagger with Finch**: Run Genie at 6 AM, Finch at 8 AM (both Sunday) to avoid overlap.

## Ontology Types

Genie does not extract entities and does not emit Signals to Elephas. Genie operates on filesystem objects (logs, snapshots, session files) which are not part of the OCAS ontology.

## Journal Outputs

Genie emits **Action Journals** — every cleanup run writes files, compresses, or deletes data (external side effects on the filesystem).

Journal file location: `{agent_root}/commons/journals/ocas-genie/YYYY-MM-DD/{run_id}.json`

## Storage Layout

See `references/genie-storage-layout.md` for the directory structure.

## Default Config

See `references/default-config-genie.md` for the default config.json.

## OKRs

See `references/okrs-genie.md` for the full OKR table.

## Background Tasks

| Job name | Mechanism | Schedule | Command |
|---|---|---|---|
| `genie:weekly-cleanup` | cron | `0 6 * * 0` (Sunday 6am) | `genie.clean` |
| `genie:update` | cron | `0 0 * * *` (midnight daily) | `genie.update` |

## Initialization

On first invocation:

1. Create `{agent_root}/commons/data/ocas-genie/` if absent
2. Write default `config.json` with ConfigBase fields if absent
3. Create `{agent_root}/commons/journals/ocas-genie/` directory
4. Log initialization as a DecisionRecord in `decisions.jsonl`
5. Register `genie:weekly-cleanup` cron job (check existing jobs first)
6. Register `genie:update` cron job (check existing jobs first)

## Self-Update

See `references/self-update-genie.md`.

## Relationship to Other Skills

- **ocas-finch**: Finch handles per-skill cleanup (stale journals, empty directories, skill-internal artifacts). Genie handles VPS-level cleanup (state snapshots, logs, cron output, session JSONs).
- **ocas-custodian**: Custodian monitors gateway logs and fixes operational failures. Genie is proactive cleanup; custodian is reactive fix.

## Execution Discipline

- **Compound instructions are atomic.** If the user says "do 1 & 2", execute ALL parts before reporting status. Never stop mid-part and ask "want me to continue?" — just finish it. Only ask for confirmation when the cleanup exceeds what was requested (e.g., the user asked for Tier 1 but you're considering Tier 2).
- **When built-in targets are small:** If the script's `--assess` shows minimal Tier 1 targets (< 500 MB reclaimable), proactively investigate the next largest directories: `backups/`, `.local/`, `archive/`, `node/`, and `.npm/`. Report findings and recommend actions. Don't stop at "script found nothing" — the script only knows its configured paths.
- **Check for ARCHIVE_STATE.md / README / rollback docs** before deleting any `archive/` or `backups/` directory. These documents explain what the archive contains and how to restore it. If found, summarize the archive's purpose and confirm deletion with the user.
- **Duplicate database detection:** When investigating `archive/` directories, check whether `.lbug` or `.db` files inside are duplicated by live copies elsewhere (e.g., `commons/db/chronicle/` vs `archive/chronicle-plugin/commons-db/`). If the live copy is healthy and current, the archive copy is a candidate for deletion even if the archive's own rollback doc lists it. Flag the duplicate for user confirmation.

## Gotchas

- **Snapshot directory mtime**: Directory mtime updates when files are created inside it. Genie checks the oldest file inside the snapshot, not the directory itself.
- **Snapshot structure varies by era**: Snapshots from different periods have different internal structures. Older snapshots may contain full environment backups and are much larger. Newer snapshots may only contain `state.db` and a few config files. See `references/snapshot-structures.md` for the breakdown.
- **Snapshot retention is user-managed**: ALWAYS ask the user before deleting a snapshot, even if it exceeds the age threshold. Snapshots are the only rollback mechanism. **EXCEPTION — Emergency disk-100%**: When `/` is at 100% and blocking critical operations (MCP auth, cron execution), delete snapshots WITHOUT user confirmation to restore functionality. State-snapshots are pre-update rollback points — they are the safest and largest deletion target. Document what was deleted for audit.
- **Snapshot backup requires credential redaction**: When backing up snapshots to git/GitHub LFS, `auth.json`, `config.yaml`, and `.env` files contain API keys, OAuth tokens, and secrets. NEVER commit these as-is. Replace with redacted stubs before committing. Only `state.db` and `state.db-journal` are safe to push directly. See `references/snapshot-backup-redaction.md`.
- **Gzip empty file artifact**: After compressing a log, a 0-byte original may remain. The .gz has all the data.
- **Snapshot compression as space recovery**: When disk is critically full and snapshot deletion is unacceptable (user-managed rollback), compressing `state.db` inside snapshots is the correct middle ground — it preserves the rollback capability while typically saving 50-75% of the space. After gzip, **always remove the original uncompressed file** to actually reclaim space. Verify the `.gz` passes `gzip -t` before removing the original.
- **Concurrent gzip race**: When compressing large files, ensure only ONE gzip process targets a file at a time. A timed-out foreground command can leave a background shell that later spawns a second gzip, resulting in both `file` and `file.gz` coexisting — zero space reclaimed. Use `gzip -t` after compression completes to verify, and if both file and .gz exist, remove the uncompressed original (after verifying the .gz is valid).
- **gzip -t timeouts scale with file size**: For multi-GB files, `gzip -t` can take minutes. A 5G file may need 60-120s, a 10G file 3-5min. Use `timeout 300 gzip -t <file>` or larger. Do NOT assume a gzip is corrupt just because the check takes a long time — it's just reading every byte.
- **Off-hermes .cache consumers**: When `/root/.cache` is large, the usual culprits are: `ms-playwright/` (browser binaries, 1G+ rebuildable), `puccinialin/` (cargo/rustup cache, rebuildable), `chroma/` (embedding DB — check before deleting). These are all Tier 1 safe rebuildable caches. Target them before touching hermes-owned paths.

- **`/tmp` not in assess output**: The `genie.py --assess` command does NOT report `/tmp/` contents, even when they contain gigabytes of reclaimable stale data. When assess shows zero or minimal Tier 1 targets but disk is still high, always manually check `/tmp/` with `du -sh /tmp/` and `find /tmp -type f -size +50M -mtime +1`. Look for stale browser data directories (Chrome/Electron profiles with `Default/`, `BrowserMetrics-*.pma`), stale git repo copies from rebase operations, and large archives. All `/tmp/` files older than 24h are Tier 1 zero-risk deletions.
- **Pre-update backup zips in `backups/`**: When investigating `backups/`, the most common large targets are `pre-update-*.zip` files — full environment archives created before Hermes updates. If the system reports "Up to date" and the zips are >24h old, these are safe to delete. Watch for near-duplicate pairs (two zips created within seconds of each other with nearly identical sizes — one is a retry, delete the smaller one). Always confirm system stability before deleting, but no ARCHIVE_STATE.md is needed for plain zip files.
- **Corrupt .gz with existing original**: If `gzip -t` reports a `.gz` file is corrupt but the uncompressed original still exists, NEVER delete the original. The corrupt gzip means the compressed copy lost data. Keep the original and regenerate the gzip (`gzip <original>`). Only delete the original after verifying the new `.gz` passes `gzip -t`. Deleting the original while the gzip is corrupt causes irreversible data loss (the session data may also be in state.db, but the file-level backup is gone).
- **Nested directory traversal**: Ensure `os.walk()` is used for recursive directory traversal. Always use `dirpath` from `os.walk()` — never rejoin filenames against the root path. See `references/os-walk-pitfall.md` for the bug that prompted this rule.
- **Large file counts**: With 5,000+ files to gzip, use `terminal(background=True, notify_on_complete=True)`.
- **Disk-at-100% blocks operations**: When disk is at 100%, Genie cannot write journal files, create temp files, or stage data. Check `df -h /` first — if at 100%, focus on immediate space recovery (Tier 1 cleanup, snapshot deletion) before attempting any backup workflow.
- **FTS footprint is significant**: FTS trigram indexes add substantial overhead proportional to message count. For large DBs (100K+ messages), expect FTS overhead in the multi-GB range. FTS can be dropped and rebuilt on demand — it contains no unique data, only search indexes.
- **VACUUM INTO rebuilds FTS indexes**: `VACUUM INTO` on a DB with FTS tables rebuilds all FTS indexes during the copy. The result is as large as the input — it does NOT compact FTS overhead. To truly compact: copy the DB, drop FTS tables on the copy, then `.backup` to a new file. See `references/state-db-compaction.md`.
- **SQLite timeouts on large state.db**: Large state.db files cause Python sqlite3 queries (especially `dbstat` and `COUNT(*)` on tables with 100K+ rows) to timeout at 30-60s. Use the `sqlite3` CLI binary for lightweight queries (`PRAGMA page_count`, table listing). Avoid `dbstat` aggregation on large DBs.
- **Script/version desync during self-update**: The SKILL.md frontmatter `metadata.version` tracks the *skill* version. The `genie.py` script is a *component* that can receive patches independently without a version bump. During `genie.update`, always compare script hashes even when versions match — see `references/self-update-genie.md` for the hash comparison procedure.
- **`~` path resolution in cron context**: When running as a cron job, `HOME` is set to the profile-scoped path (`/root/.hermes/profiles/indigo/home/`), not `/root/`. The `read_file` tool expands `~` to this profile home, causing "file not found" errors for paths like `~/.hermes/scripts/genie.py`. **Always use absolute paths** (`/root/.hermes/...`) in cron context. The `terminal` tool does not have this issue — it resolves `~` from the actual user home.
- **GitHub default branch is `main`**: The genie repo's default branch is `main`, not `master`. Using `master` in raw GitHub URLs returns 404 or stale content. See `references/self-update-genie.md` for the correct URLs.

## Support File Map

| File | When to read |
|---|---|
| `references/operational-notes.md` | Before first production run — real-world examples. Also contains the 2026-06-08 zero-target /tmp investigation case. |
| `references/os-walk-pitfall.md` | When debugging nested directory traversal issues |
| `references/session-2026-05-29-disk-recovery.md` | 2026-05-29 disk emergency — space recovered per target, gzip race pitfall, realistic gzip -t timeouts on multi-GB files |
| `references/snapshot-backup-redaction.md` | When backing up snapshots to git/LFS — credential redaction procedure |
| `references/snapshot-structures.md` | When analyzing snapshots — 9-file full format vs 5-file minimal format, size breakdowns, and analysis commands |
| `references/state-db-compaction.md` | When tackling state.db bloat — measured results, failed approaches, and the correct procedure |
| `references/state-db-size-breakdown.md` | When analyzing state.db composition — size breakdown by component, ratios, and the key insight that most of the DB is real data not bloat |
| `scripts/genie.py` | The main cleanup script — run via terminal(background=True) for large file counts |
| `scripts/genie_rebuild_fts.py` | FTS rebuild script — run after restoring a no-FTS backup to recreate all FTS indexes and triggers |

## Verification

After running, verify with:
- `df -h /` — check disk usage dropped
- `du -sh /root/.hermes/` — check .hermes size
- Session search still works (confirms state.db intact)

## Testing New Changes

When modifying `genie.py`, validate with a fixture directory before running against production. See `references/operational-notes.md` for the test fixture script.

**Key pitfall**: when walking nested directories (e.g. `cron/output/`), always use `dirpath` from `os.walk()` — never rejoin filenames against the root path.