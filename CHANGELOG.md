# Changelog

All notable changes to the genie skill are documented here.

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
