# Maintenance Lessons — Publishing and Silent No-Ops

Two failure modes that cost real time: changes that never reach the remote, and
retention code that reports success while doing nothing.

## Publishing a genie.py change when the remote was force-updated

The live skill dir `~/.hermes/profiles/indigo/skills/ocas-genie` **IS its own
git repo** (remote `indigokarasu/genie`). A scheduled sync can clobber unpushed
edits, so PUSH FROM THE LOCAL SKILL REPO, never from a `/tmp` clone.

If `git push` is rejected because the remote advanced (and `fetch` shows
`(forced update)`), a plain `rebase origin/main` may CONFLICT in
`references/*.md` (the remote's PII-sanitize/beautify commits). Those are
doc-only and unrelated to `genie.py`; resolve each conflicting doc commit with:

    git checkout --theirs -- references/
    git rebase --skip

Your `genie.py` commit (a different file) then applies cleanly on top. Push
**without `--force`** — never clobber remote work — then verify
`git rev-list --count HEAD..origin/main` is 0. If an unrelated uncommitted edit
(e.g. README) is present, stash it before rebasing; do not bundle it.

## A retention line pointing at a nonexistent path is a silent no-op

A nightly prune ran `git -C <fs-root>/indigo lfs prune` for two months — but the
repository is `<fs-root>/indigo-repo`. `git -C` on a non-repo fails quietly, and
the line was wrapped in `>/dev/null 2>&1`, so the job reported success every day
while the LFS cache grew to 12 GB and filled the disk.

Verify every retention target resolves before trusting the line:

    [ -d "$P/.git" ] || echo "MISSING: $P"

Prefer loud failure to silent success. This is the same family as the
placeholder-token defect: code that runs, and does nothing.
