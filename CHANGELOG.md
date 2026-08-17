# Changelog

All notable changes to the genie skill are documented here.

## [1.8.0] - 2026-08-16

### Fixed
- **Data-loss defect in `clean_git_clones`.** It deleted any sufficiently old
  clone that merely had a remote configured, with no check for uncommitted
  changes, stashes, or unpushed commits — although those gates were already
  documented in `SKILL.md`. The gate is now enforced in code by
  `clone_delete_blockers()`, which fails closed on any unreadable repo.
  See `references/clone-deletion-safety.md`.
- Removed an operator-identifying hostname from an example in `SKILL.md`
  (protected paths are now expressed generically and configured via
  `git_clones_protected`).

- **Retention targeted the live backup copy set.** `historical_backup_candidates()`
  documented that live databases were excluded, but added every entry in a
  backup root — so the current DB copies the backup pipeline refreshes in
  place were treated as redundant history and deleted on `--clean`. Only
  dated directories, dated files, and archives are candidates now.

### Added
- **Backup-freshness gate.** With a `backup_stamps_path` present, genie
  reports each backup path's age in `--assess` and refuses backup-class
  cleanup while any is stale — the local copy is the only copy exactly when
  the pipeline has stopped.
- `tests/test_clone_delete_gate.py` (7 cases) and
  `tests/test_backup_retention_scope.py` (9 assertions) — the skill had no
  tests before this release.
- `references/clone-deletion-safety.md`, plus the 2026-08-16 reclaim patterns
  (LFS caches, orphaned runtimes, GPU stacks, duplicate model stores) in
  `references/disk-growth-patterns.md`.
- Config: `git_clones_protected`, `backup_stamps_path`,
  `backup_stamp_max_age_hours`.

## [1.7.1] - 2026-08-16

### Fixed
- Restored real runtime paths in `genie.py` that an earlier sanitization pass
  had replaced with `<fs-root>` placeholder tokens — the tokens had silently
  disabled inactive-git-clone pruning and historical-backup retention. Paths
  now derive from the running user's home directory (`FS_ROOT`), so the code
  stays generic without tokenization.
- Backup-validity check uses the real database filenames again.
- Rebuilt `README.md` (structure was mangled by the same sanitization pass)
  and aligned the `skill.json` version with the skill.

### Added
- Per-run journaling to `commons/journals/ocas-genie/runs.jsonl` (fail-safe:
  a journaling error can never break a run).
- `--help` flag for `genie_rebuild_fts.py`.
- `LICENSE` file (MIT).

## [1.1.0] - 2026-05-23

### Added
- OCAS architecture compliance: Responsibility Boundary, Ontology Types, Journal Outputs, Storage Layout, OKRs, Background Tasks, Initialization, and Self-update sections
- `skill.json` with ConfigBase fields and self-update configuration
- `.gitignore` for skill package
- README.md and CHANGELOG.md
- `genie:update` cron job for daily self-updates from GitHub
- `genie:weekly-cleanup` cron job registration during initialization

### Changed
- Frontmatter updated to include `metadata` block (author, version, tags, category)
- Version bumped from 1.0.0 to 1.1.0

## [1.0.0] - 2026-04-20

### Added
- Initial OCAS integration
- VPS disk monitoring and safe cleanup
- Three-tier safety model (zero risk, low risk, analysis-only)
- Configurable thresholds via environment variables
- Cron job support (weekly Sunday 6 AM)
- Dry-run mode
- Background execution for large file counts