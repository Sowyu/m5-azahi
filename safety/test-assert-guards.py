#!/usr/bin/env python3
"""Safety checks that silently vanish: asserts under python -O, "! cmd" under set -e.

Every non-test script in these directories that contains an assert must refuse
to start under -O, before any import side effect or file access.
"""
import ast
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
AREAS = ('probe', 'ramroot', 'remote-access', 'safety', 'standalone-loader', 'usb-driver')


def guarded_scripts():
    tracked = subprocess.run(['git', 'ls-files', '--', *AREAS], cwd=ROOT, check=True,
                             capture_output=True, text=True).stdout.split()
    for name in tracked:
        path = ROOT / name
        if path.suffix != '.py' or path.name.startswith('test-'):
            continue
        tree = ast.parse(path.read_text())
        imports = {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import)
                   for alias in node.names}
        if 'unittest' not in imports and any(isinstance(n, ast.Assert) for n in ast.walk(tree)):
            yield path


class AssertGuards(unittest.TestCase):
    def test_optimized_run_refused(self):
        scripts = list(guarded_scripts())
        self.assertGreaterEqual(len(scripts), 11)
        with tempfile.TemporaryDirectory(prefix='azahi-assert-guard-') as temporary:
            for script in scripts:
                with self.subTest(script=script.relative_to(ROOT)):
                    result = subprocess.run([sys.executable, '-O', str(script)], cwd=temporary,
                                            capture_output=True, text=True, timeout=30)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn('Refusing python -O', result.stderr)
            self.assertEqual(list(Path(temporary).iterdir()), [])

    def test_no_negated_guard_under_errexit(self):
        # bash set -e ignores a command negated with "!", so "! cmd" never aborts.
        tracked = subprocess.run(['git', 'ls-files', '--', *AREAS], cwd=ROOT, check=True,
                                 capture_output=True, text=True).stdout.split()
        shells = [ROOT / n for n in tracked if n.endswith('.sh')]
        self.assertIn(ROOT / 'usb-driver/build.sh', shells)
        for path in shells:
            for number, line in enumerate(path.read_text().splitlines(), 1):
                self.assertFalse(line.lstrip().startswith('! '), f'{path.name}:{number}')


if __name__ == '__main__':
    unittest.main(verbosity=2)
