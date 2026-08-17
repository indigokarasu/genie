# Clone deletion safety (incident + gate)

## What happened (2026-08-16)

`clean_git_clones()` deleted any directory under the clones path that was
(1) a git repo, (2) had a `url =` line in `.git/config`, and (3) was older
than `git_clone_max_age_days`. That is all it checked. `SKILL.md` meanwhile
documented four further gates — clean tree, no stashes, no unpushed commits,
protected paths — none of which existed in code.

The gap was invisible for weeks because the feature was itself dead: a
sanitization pass had replaced the clones path with a literal `<fs-root>`
placeholder, so the scan pointed at a path that does not exist. Restoring the
real path re-armed the unguarded deletion, and the next `--clean` removed a
905 MB clone.

That clone turned out to be a pristine third-party reference checkout whose
HEAD existed on its public remote, so nothing unique was lost — but that was
luck. The same code would have deleted a clone holding unpushed commits.

**Two lessons.** A documented gate that is not in code does not exist. And
re-enabling a dormant destructive feature is a change that deserves the same
review as writing it fresh — audit what it will do *before* the first run.

## The gate (v1.8.0)

`clone_delete_blockers(path, protected)` returns a list of reasons a clone
must not be deleted; empty means safe. It **fails closed**: any probe that
errors returns a blocker, so an unreadable repo is never deleted.

| Blocker | Probe |
|---|---|
| protected path | basename/substring match against `git_clones_protected` |
| uncommitted changes | `git status --porcelain` non-empty |
| stashed work | `git stash list` non-empty |
| unpushed commits | per branch: `git rev-list --count <upstream>..<branch>` != 0 |
| unverifiable branch | branch has no configured upstream |
| unreadable repo | any git probe fails |

Covered by `tests/test_clone_delete_gate.py` (7 cases, including the
fail-closed and protected-path paths).

## Proving a clone is disposable by hand

`ahead=0` alone is not proof. Use these, in order of strength:

1. **Patch-equivalence** — `git cherry <remote-branch> HEAD`; every line
   prefixed `-` is already upstream. This survives rebases, where commit IDs
   differ but the content is present.
2. **Commit existence on the remote** — for a public host, query the API for
   the SHA (`gh api repos/<owner>/<repo>/commits/<sha>`). A 200 proves the
   object is on the server, not merely that a local ref agreed.
3. **Every branch, not just HEAD** — enumerate `refs/heads` and check each
   one; work is routinely stranded on a side branch.

If a clone cannot pass these, it is not cleanup — it is deletion of the only
copy. Report it and let the owner decide.
