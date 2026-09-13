#!/usr/bin/env python3
"""Run the enrollment regression suite with actual restored-V5/v3 pins."""
import functools
from pathlib import Path
import runpy
import tarfile
import unittest

HERE = Path(__file__).resolve().parent
T = runpy.run_path(str(HERE / 'test-install.py'))
S = T['S']
old_validate = S['validate_after']
CONTROL = HERE.parent / 'logs/standalone-enroll-20260911.AO0gTd/rollback-after.tar.gz'


class AlignedTests(T['InstallTests']):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.baseline, cls.script = S['aligned_profile'](T['BACKUP'], CONTROL)
        with tarfile.open(CONTROL) as archive:
            control = {m.name: archive.extractfile(m).read() for m in archive}
        cls.fixture = control
        for name in ('policy-before.txt', 'policy-rechecked.txt', 'policy-after.txt'):
            cls.fixture[name] = control['policy-after.txt']
        cls.backup['boot-policy.txt'] = control['policy-after.txt']
        cls.backup['custom-02.bin'] = control['installed.bin']
        lines = cls.backup['manifest.tsv'].decode().splitlines()
        lines[1] = 'custom-02.bin\t' + control['installed-path.txt'].decode().strip()
        cls.backup['manifest.tsv'] = ('\n'.join(lines) + '\n').encode()
        cls.candidate_path = HERE.parent / 'standalone-ssdroot-v3-aligned-20260912.bin'
        S['CANDIDATE'] = S['ALIGNED_CANDIDATE']
        S['validate_after'] = functools.partial(old_validate,
            candidate=S['ALIGNED_CANDIDATE'], candidate_size=92651520)

    def test_control_backup_and_template_pins(self):
        self.assertIn('750659463 92651520', self.script)
        self.assertIn('2129482942 1117033', self.script)
        self.assertIn(S['CONTROL_COIH'], self.script)
        self.assertNotIn('819284573 92651350', self.script)


if __name__ == '__main__':
    unittest.main()
