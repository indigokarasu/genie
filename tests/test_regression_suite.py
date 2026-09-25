#!/usr/bin/env python3
"""unittest entry point for genie's regression suites.

The two suites are plain scripts (`python3 tests/test_*.py`) rather than
TestCase classes, so `python3 -m unittest discover -s tests` used to report
"NO TESTS RAN" — the CI/audit signal said the skill had no working tests even
though both suites pass. This adapter loads each script in-process (real code
path, no subprocess re-import) and asserts its exit status.

Run either way:
    python3 tests/test_regression_suite.py
    python3 -m unittest discover -s tests
"""
import importlib.util
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, HERE)

SUITES = ("test_backup_retention_scope", "test_clone_delete_gate")


def _load(module_name):
    """Import a sibling regression script as a module, in-process."""
    path = os.path.join(HERE, module_name + ".py")
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None, "cannot load %s" % path
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class RegressionSuites(unittest.TestCase):
    """One test per suite so a failure names the suite that broke."""

    def _run_suite(self, module_name):
        module = _load(module_name)
        rc = module.main()
        self.assertEqual(
            rc, 0,
            "%s FAILED: %s" % (module_name, ", ".join(module.FAILURES) or "see output above"))

    def test_backup_retention_scope(self):
        self._run_suite("test_backup_retention_scope")

    def test_clone_delete_gate(self):
        self._run_suite("test_clone_delete_gate")


if __name__ == "__main__":
    unittest.main(verbosity=2)
