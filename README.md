# Genie

VPS disk space monitor and safe cleanup for the OCAS agent. Identifies cleanup targets, estimates space reclamation, and executes safe deletions without reducing functionality.

**OCAS skill** — part of the OCAS infrastructure layer.

## Overview

Genie monitors disk usage on the Hermes VPS and performs safe, tiered cleanup operations. Designed to run as a weekly cron job or on-demand.

## Commands

- `genie.clean` — assess, dry-run, and clean (full workflow)
- `genie.assess` — report current disk usage and cleanup targets only
- `genie.update` — self-update from GitHub source

## What Gets Cleaned

1. Stale state snapshots (older than 7 days)
2. Old log files (compressed after 7 days, deleted after 30)
3. Old cron output (compressed after 7 days)
4. Session JSON duplicates (compressed after 14 days)
5. state.db bloat analysis (report only, never modifies)

## Dependencies

- Python 3.11+
- `gh` CLI for self-update
- Standard library only (no pip packages)

## Scheduled Tasks

Weekly cleanup: Sundays at 6 AM (staggered with Finch at 8 AM).

## Changelog

See CHANGELOG.md.
