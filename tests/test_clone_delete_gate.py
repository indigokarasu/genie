#!/usr/bin/env python3
"""Regression test for genie's clone-deletion safety gate.

History: clean_git_clones deleted any sufficiently old clone that merely had a
remote configured. It never checked for uncommitted changes, stashes, or
unpushed commits — though SKILL.md documented all of those as required gates.
On 2026-08-16 it destroyed a real clone on the production box. These cases
lock the gate shut: a clone is deletable only when every byte it holds also
exists somewhere else.

Run: python3 tests/test_clone_delete_gate.py
"""
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import genie  # noqa: E402

FAILURES = []


def sh(*args, cwd=None):
    subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True)


def git(repo, *args):
    sh("git", "-C", repo, *args)


def make_clone(root, name, origin):
    path = os.path.join(root, name)
    sh("git", "clone", "-q", origin, path)
    git(path, "config", "user.email", "test@example.com")
    git(path, "config", "user.name", "test")
    return path


def check(label, blockers, expect_safe, expect_substr=None):
    if expect_safe:
        ok = blockers == []
    else:
        ok = bool(blockers) and (expect_substr is None or
                                 any(expect_substr in b for b in blockers))
    print("%-28s %-6s %s" % (label, "PASS" if ok else "FAIL", blockers))
    if not ok:
        FAILURES.append(label)


def main():
    root = tempfile.mkdtemp(prefix="genie-gate-")
    try:
        origin = os.path.join(root, "origin.git")
        sh("git", "init", "-q", "--bare", "-b", "main", origin)

        seed = make_clone(root, "seed", origin)
        with open(os.path.join(seed, "f.txt"), "w") as fh:
            fh.write("hello\n")
        git(seed, "add", "f.txt")
        git(seed, "commit", "-q", "-m", "init")
        git(seed, "push", "-q", "-u", "origin", "main")

        # 1. clean + fully pushed -> deletable
        clean = make_clone(root, "clean", origin)
        check("clean+pushed", genie.clone_delete_blockers(clean), True)

        # 2. uncommitted working-tree change -> blocked
        dirty = make_clone(root, "dirty", origin)
        with open(os.path.join(dirty, "f.txt"), "a") as fh:
            fh.write("local edit\n")
        check("uncommitted change", genie.clone_delete_blockers(dirty), False, "uncommitted")

        # 3. committed but unpushed -> blocked
        unpushed = make_clone(root, "unpushed", origin)
        with open(os.path.join(unpushed, "new.txt"), "w") as fh:
            fh.write("work that exists only here\n")
        git(unpushed, "add", "new.txt")
        git(unpushed, "commit", "-q", "-m", "local only")
        check("unpushed commit", genie.clone_delete_blockers(unpushed), False, "unpushed")

        # 4. branch with no upstream -> unverifiable, blocked
        noup = make_clone(root, "noup", origin)
        git(noup, "checkout", "-q", "-b", "feature")
        check("branch without upstream", genie.clone_delete_blockers(noup), False, "no upstream")

        # 5. stashed work -> blocked
        stashed = make_clone(root, "stashed", origin)
        with open(os.path.join(stashed, "f.txt"), "a") as fh:
            fh.write("stash me\n")
        git(stashed, "stash")
        check("stashed work", genie.clone_delete_blockers(stashed), False, "stash")

        # 6. not a git repo -> fails closed
        plain = os.path.join(root, "plain")
        os.makedirs(plain)
        check("not a repo (fail closed)", genie.clone_delete_blockers(plain), False)

        # 7. protected path -> blocked even when clean
        check("protected path", genie.clone_delete_blockers(clean, ["clean"]), False, "protected")

        # 8. detached HEAD with a local commit -> blocked (no branch holds it)
        detached = make_clone(root, "detached", origin)
        git(detached, "checkout", "-q", "--detach")
        with open(os.path.join(detached, "detached.txt"), "w") as fh:
            fh.write("work reachable from no branch\n")
        git(detached, "add", "detached.txt")
        git(detached, "commit", "-q", "-m", "detached work")
        check("detached HEAD", genie.clone_delete_blockers(detached), False, "detached")
    finally:
        shutil.rmtree(root, ignore_errors=True)

    print()
    if FAILURES:
        print("FAILED: %s" % ", ".join(FAILURES))
        return 1
    print("ALL 8 GATE CASES PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
