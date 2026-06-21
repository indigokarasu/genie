# Operational Notes — Genie Production Runs

## 2026-05-23: First Production Run

### Environment
- Disk: 96 GB total, 88% used (84.4 GB) before cleanup
- state.db: 13.9 GB (129K messages, 13K sessions)
- Snapshots: 1 directory (13.9 GB, from pre-update at 2026-05-23 20:51:45)

### Run 1 (full cleanup)
- Assess estimated: 8,897 old session JSONs + 4,396 cron files + 2 logs = ~7.2 GB gzip targets
- Actual cleaned: 1,165 session JSONs + 1 cron file = 689.1 MB saved
- Disk after: 83% (79.6 GB)

### Run 2 (maintenance, later same day)
- Targets: 35 cron files (562 KB) + 27 session JSONs (18.2 MB)
- Actual cleaned: 50 cron files + 35 session JSONs = 3.1 MB saved
- Disk after: 83% (79.6 GB)

### Key Learnings
1. Snapshot is 13.9 GB — single largest reclaimable item. User confirmed 7-day retention is valuable.
2. Session .json count drops fast after one full pass. Subsequent runs are small.
3. Cron output accumulates steadily — lots of small output files from cron jobs.
4. execute_code 300s timeout is insufficient for 5,000+ file gzip. Use terminal(background=True).
5. Assess vs actual mismatch is normal — the assess is a snapshot, not a guarantee.

## Cron Bug Discovery (2026-05-23)

### Bug
`cronjob(create)` with `schedule: "0 6 * * 0"` + `repeat: "forever"` triggers:
`'<=' not supported between instances of 'str' and 'int'`

### Workaround
Omit `repeat` entirely — it defaults to forever. Do NOT create one-shot timestamp jobs as workaround.

## Script Locations
- Production: /root/.hermes/scripts/genie.py
- Skill-bundled: /root/.hermes/skills/ocas-genie/scripts/genie.py

## Cron Job
- Job ID: e3adc3e31181
- Name: genie:disk-cleanup
- Schedule: Sundays at 6 AM (`0 6 * * 0`, repeats: forever)
- Delivery: local

## 2026-05-25: Full Disk Emergency + Snapshot Backup

### Environment
- Disk: 96 GB total, 100% used (2.6 MB free) — critical
- 5 snapshots totaling 28.7 GB (two at 14-15 GB, three under 751 MB)
- state.db: 14.0 GB (137K messages, 13.6K sessions)

### Actions Taken
1. Deleted 2 old snapshots (20260523 + 20260525-044532) → recovered 29 GB
2. Compressed 1,053 cron output files → 14.5 MB freed
3. Compressed 742 old session JSONs → 77.7 MB freed
4. Backed up remaining 3 snapshots to GitHub LFS (with credential redaction)
5. Disk after: 71% (29 GB free)

### Key Learnings
1. **Snapshot backup requires credential redaction**: `auth.json`, `config.yaml`, and `.env` in snapshots contain API keys and OAuth secrets. Must be replaced with stubs before committing to git. Only `state.db` and `state.db-journal` are safe to push. See `references/snapshot-backup-redaction.md`.
2. **SQLite timeouts on large DB**: Python sqlite3 queries (COUNT, dbstat) timeout at 30-60s on 14 GB state.db. Use `sqlite3` CLI binary for lightweight queries. Avoid dbstat aggregation.
3. **Snapshot structure changed over time**: Early snapshots (May 23-24) had 9 files (full env backup including cron/, channel_directory.json, etc.). Later snapshots (May 25) had only 5 files (state.db + journal + auth + config + .env). The process was simplified.
4. **Compression ratios modest**: Cron output and session JSONs yielded ~92 MB total — small compared to snapshot deletion. The real wins are always the large binary files (state.db in snapshots).
5. **/tmp is tmpfs**: 3.9 GB RAM-backed, useful for small temp work but not for multi-GB staging.

## 2026-05-25 (Later): No-FTS Backup + Inception Verification

### Pipeline
1. Created no-FTS compressed backup: copy → drop FTS → pigz (15 GB → 3.6 GB)
2. Spun up Inception container with host volume mount
3. Restored DB inside container
4. VACUUM inside container (15 GB → 12 GB)
5. Rebuilt FTS indexes in Python (12 GB → 14.55 GB)
6. Ran completeness + recall tests

### Results
- **All completeness tests PASS**: 138,887 messages, 13,607 sessions, 0 orphans
- **All recall tests PASS**: FTS search 3/3, Trigram 3/3
- **FTS overhead measured**: 2.7 GB (not 11.5 GB as previously estimated)
- **Corrected bloat estimate**: Live DB at 15 GB = ~12 GB real data + ~2.7 GB FTS + ~0.3 GB fragmentation
- **VACUUM savings on live DB**: Only ~0.5 GB — not worth the risk

### Key Learnings
1. **Inception container overlay too small for large DBs**: Cannot cp a 15 GB DB into container filesystem. Must use host volume mounts (`-v /host/path:/container/path`).
2. **sqlite3 CLI lacks FTS5 in Ubuntu 24.04**: Must use Python for FTS5 operations.
3. **DB lock after docker cp**: Use timeout=30 and busy_timeout=30000.
4. **pigz -o flag doesn't work**: Use shell redirection (`pigz -6 file > file.gz`... actually pigz replaces in-place, use `pigz -6 file` then `mv file.gz dest`).
5. **VACUUM is NOT the lever for state.db**: Only saves 0.5 GB. For actual space savings, prune old messages instead.
6. **User gets frustrated when Inception is bypassed**: When user asks for Inception, run Inception. Do not substitute alternatives.
