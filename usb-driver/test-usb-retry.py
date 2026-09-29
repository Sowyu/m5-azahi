#!/usr/bin/env python3
"""Host test for azahi-usb-start-retry.sh: only a clean HPM refusal retries."""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

WRAPPER = Path(__file__).resolve().parent / 'azahi-usb-start-retry.sh'


def run(start_status, result, poisoned, loaded=True):
    with tempfile.TemporaryDirectory() as folder:
        folder = Path(folder)
        params = folder / 'params'
        if loaded:
            params.mkdir()
            (params / 'result').write_text(result)
            (params / 'poisoned').write_text(poisoned)
        start = folder / 'start'
        start.write_text(f'#!/bin/sh\nexit {start_status}\n')
        start.chmod(0o755)
        env = dict(os.environ, AZAHI_HPM_PARAMS=str(params), AZAHI_USB_START=str(start))
        done = subprocess.run(['bash', str(WRAPPER)], env=env, capture_output=True, text=True)
        return done.returncode, done.stdout


class Retry(unittest.TestCase):
    def test_success_passes_through(self):
        self.assertEqual(run(0, '0', 'N')[0], 0)

    def test_clean_refusal_requests_retry(self):
        code, out = run(1, '-11', 'N')
        self.assertEqual(code, 75)
        self.assertIn('USB_WAITING', out)

    def test_poisoned_refusal_never_retries(self):
        self.assertEqual(run(1, '-11', 'Y')[0], 1)

    def test_other_hpm_errors_never_retry(self):
        self.assertEqual(run(1, '-5', 'N')[0], 1)

    def test_helper_not_loaded_never_retries(self):
        self.assertEqual(run(1, '', '', loaded=False)[0], 1)

    def test_other_failure_status_is_kept_unless_clean_refusal(self):
        self.assertEqual(run(3, '0', 'N')[0], 3)


if __name__ == '__main__':
    unittest.main()
