# ⚙️ Genie

  <img src="./assets/readme/hero.jpg" width="100%" alt="Genie">

If true, only report — don't delete/compress

**Skill name:** `ocas-genie`
**Version:** 1.7.0
**Type:** 
**Layer:** infrastructure
**Author:** Indigo Karasu

---

## 📖 Overview

If true, only report — don't delete/compress

---

## 🔧 Commands

- `/root` needs a safe audit/classification pass
- `/root/backup/*`
- `/root/backups/*`
- `<hermes-root>/profiles/<profile>/state-snapshots/*` (profile-scoped — the bare `<hermes-root>/state-snapshots` is a different, usually-empty path)
- `<hermes-root>/migrations/*/backups/*`
- `<hermes-home>/skills/ocas-genie/scripts/genie.py` (profile — note `ocas-` prefix)
- `<hermes-home>/scripts/genie.py` (profile scripts dir — alternate location)
- `<hermes-root>/skills/ocas-genie/scripts/genie.py` (skill-bundled)
- `df -h /` — check disk usage dropped
- `du -sh <hermes-root>/` — check .hermes size

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
