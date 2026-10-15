"""Guard regression: stress task request/confirmation must align with research expected business meaning."""
import json
from pathlib import Path
import unittest

PRIVATE_NAME = 'AD_PRIVATE_DO_NOT_COMMIT' # no access or import
ROOT = Path(__file__).resolve().parents[1]

class StressRequestConsistencyTests(unittest.TestCase):
    def test_no_a3_private_gold_in_public_repo(self):
        self.assertFalse((ROOT/PRIVATE_NAME).exists(), 'Private Gold must never be copied into public repository')

    def test_stress03_request_is_within_structured_confirmation(self):
        # Inputs are kept sealed until authorized pressure experiment: this test checks PUBLIC version index only.
        import csv
        with (ROOT/'docs/handoff/A2_PUBLIC_RELEASE_MATRIX.csv').open(encoding='utf-8-sig',newline='') as f:rows={r['case_id']:r for r in csv.DictReader(f)}
        self.assertEqual(rows['A1-STRESS-03']['fixture_version'],'a1-stress-03-r3')
        self.assertEqual(rows['A1-STRESS-04']['fixture_version'],'a1-stress-04-r3')
        self.assertEqual(rows['A1-STRESS-03']['can_start_formal'],'NO')

if __name__=='__main__': unittest.main()
