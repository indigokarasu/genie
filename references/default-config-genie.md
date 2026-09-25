# Genie — Default Config

## Packaged config record (legacy ConfigBase shape)

```json
{
  "skill_id": "ocas-genie",
  "skill_version": "1.3.0",
  "config_version": "1",
  "created_at": "",
  "updated_at": "",
  "retention": {
    "days": 90,
    "max_records": 5000
  },
  "thresholds": {
    "snapshot_max_age_days": 7,
    "log_compress_age_days": 7,
    "log_delete_age_days": 30,
    "cron_output_compress_age_days": 7,
    "session_compress_age_days": 14
  }
}
```

## Runtime keys (`skills.config.genie.*` in config.yaml)

The live script resolves every behavioral setting through `_skill_config()`
(type-coerced from the default's type). Unset keys fall back to the defaults
below; CLI flags (e.g. `--dry-run`) override config at run time. Legacy
`GENIE_*` env vars no longer exist.

| Key | Default | Meaning |
|---|---|---|
| `snapshot_max_age_days` | 7 | Delete snapshots older than N days (newest always preserved) |
| `log_compress_age_days` | 7 | Compress logs older than N days |
| `log_delete_age_days` | 30 | Delete compressed logs older than N days |
| `cron_output_compress_age_days` | 7 | Compress cron output older than N days |
| `session_compress_age_days` | 14 | Compress session JSONs older than N days |
| `tmp_stale_hours` | 24 | Delete `/tmp` files older than N hours (0 to skip) |
| `git_clone_max_age_days` | 5 | Delete untouched clones under `<projects-root>/` (remote required) |
| `git_clones_protected` | `[]` | Basenames/paths never eligible for clone deletion |
| `git_clones_verify_remote` | true | Contact the remote before deleting a clone |
| `backup_stamps_path` | `<hermes-home>/logs/stamps` | Backup-freshness stamp dir (missing = gate inactive) |
| `backup_stamp_max_age_hours` | 26 | Max stamp age before backup-class cleanup is refused |
| `backup_stamp_ignore` | `[]` | Verification-only stamps exempt from the freshness gate |
| `dry_run` | false | Report only — never delete or compress |
| `filesystem_md` | (empty) | Optional FILESYSTEM.md override path |
| `allow_local_state_db_backup` | false | Count local full `state.db` copies as valid retained backups |
| `snapshots_path` | `<hermes-home>/state-snapshots` | Snapshot root — profile-scoped setups must override this |
