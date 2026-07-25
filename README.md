# ⚙️ Genie

  <img src="./assets/readme/hero.jpg" width="100%" alt="Genie">

If true, only report — don't delete/compress

**Skill name:** `ocas-genie`
**Version:** 1.7.0
**Type:** 
**Layer:** infrastructure
<<<<<<< Updated upstream
**Author:** Indigo Karasu
=======
**Author:** <agent-name>
>>>>>>> Stashed changes

---

## 📖 Overview

If true, only report — don't delete/compress

---

## 🔧 Commands

- `/root` needs a safe audit/classification pass
- `<fs-root>/backup/*`
<<<<<<< Updated upstream
- `<fs-root>/backups/*`
- `<hermes-home>/profiles/<profile>/state-snapshots/*` (profile-scoped — the bare `<hermes-home>/state-snapshots` is a different, usually-empty path)
- `<hermes-home>/migrations/*/backups/*`
- `<hermes-home>/profiles/indigo/skills/ocas-genie/scripts/genie.py` (profile — note `ocas-` prefix)
- `<hermes-home>/profiles/indigo/scripts/genie.py` (profile scripts dir — alternate location)
- `<hermes-home>/skills/ocas-genie/scripts/genie.py` (skill-bundled)
- `df -h /` — check disk usage dropped
- `du -sh <hermes-home>/` — check .hermes size
=======
- `<backups-root>/*`
- `~/.hermes/profiles/<profile>/state-snapshots/*` (profile-scoped — the bare `~/.hermes/state-snapshots` is a different, usually-empty path)
- `~/.hermes/migrations/*/backups/*`
- `~/.hermes/profiles/indigo/skills/ocas-genie/scripts/genie.py` (profile — note `ocas-` prefix)
- `~/.hermes/profiles/indigo/scripts/genie.py` (profile scripts dir — alternate location)
- `~/.hermes/skills/ocas-genie/scripts/genie.py` (skill-bundled)
- `df -h /` — check disk usage dropped
- `du -sh ~/.hermes/` — check .hermes size
>>>>>>> Stashed changes

---

## 📊 Outputs

See `SKILL.md` for outputs, journals, and persistence rules.

---

## 📄 Files

| File | Purpose |
|---|---|
| `SKILL.md` | Skill definition |
| `references/` | Supporting documentation |
| `scripts/` | Helper scripts |


## Changelog

- [1.1.0] - 2026-05-23
- Added
- Changed
- [1.0.0] - 2026-04-20
- Added

---

## 📚 Documentation

Read `SKILL.md` for operational details, schemas, and validation rules.

Read `references/` for detailed specifications and examples.


---

## 📄 License

MIT License — see `LICENSE` for details.