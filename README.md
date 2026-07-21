# genie

<p align="center">
  <img src="./assets/readme/hero.jpg" width="100%" alt="Genie: VPS disk cleanup and backup retention management">
</p>

Genie audits disk usage on a VPS, cleans up safely, and manages backup retention. It runs from the terminal, uses standard libraries only, and has no external dependencies. The self-update path uses `gh` for release fetches.

**Capabilities:**
- Root filesystem audit with summary breakdown
- Safe cleanup targets (logs, cache, old archives)
- Backup retention with configurable age thresholds
