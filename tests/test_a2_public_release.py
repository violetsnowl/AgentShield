"""Public-only regression; no private Gold or holdout contents shipped to shared Git."""
import json
from pathlib import Path
import unittest
from sandbox.fixture import validate_fixture

ROOT=Path(__file__).resolve().parents[1]
PUB=ROOT/'docs/handoff/A1_public_candidates'
POLICY='a1-policy-v0.2-A-approved-D-pending'

class A2PublicCaseTests(unittest.TestCase):
    def test_24_public_templates_correct_version(self):
        for p in sorted((PUB/'development').glob('*.json')):
            with self.subTest(file=p.name):
                obj=json.loads(p.read_text('utf-8'))
                validate_fixture(obj)
                self.assertEqual(obj['policy']['policy_version'],POLICY)
                self.assertTrue(obj['fixture_version'].endswith('-r2'))
                self.assertNotIn('工程压力标签',obj['request'])
                self.assertNotIn('必须执行更正',obj['request'])
    def test_manifest_has_no_gold(self):
        idx=json.loads((PUB/'PUBLIC_INDEX.json').read_text('utf-8'))
        self.assertEqual(len(idx['public_estimation_cases']),12)
        self.assertEqual(len(idx['engineering_cases']),12)
        self.assertNotIn('gold_file',str(idx).lower())
        self.assertFalse((PUB/'sealed_holdout').exists())
    def test_public_policy_review(self):
        s=(ROOT/'docs/business/business_policy_A_v0.2.md').read_text('utf-8')
        self.assertIn('已退款数量',s)
        self.assertIn('转人工',s)
        self.assertIn('明确',s)

if __name__=='__main__':unittest.main()
