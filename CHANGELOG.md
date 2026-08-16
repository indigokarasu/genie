# Changelog

All notable changes to the genie skill are documented here.

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