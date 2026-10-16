import ast,importlib,unittest
from pathlib import Path
from evaluator.loss import compute_loss
from evaluator.obligations import validate_spec
from scripts import a2_release_audit

class A4PublicReleaseTests(unittest.TestCase):
    def test_a2_audit_no_dependency_on_missing_preflight(self):
        src=Path(a2_release_audit.__file__).read_text(encoding='utf-8')
        self.assertNotIn('from scripts.a1_preflight import',src)
        self.assertTrue(callable(a2_release_audit.verify))
        self.assertTrue(callable(a2_release_audit.audit))
    def test_no_automatic_approval(self):
        self.assertTrue(callable(a2_release_audit.verify))
    def test_known_refund_does_not_equal_loss(self):
        rows=[{'ref':'primary','committed_cents':15630,'legally_due_cents':15630},
              {'ref':'accessory','committed_cents':0,'legally_due_cents':0}]
        v=compute_loss(rows,0);self.assertEqual(v['net_loss_cents'],0)
        self.assertEqual(v['loss_status'],'verified')
    def test_unknown_due_no_outflow_no_cash_loss_but_underpayment_unknown(self):
        rows=[{'ref':'gift','committed_cents':0,'legally_due_cents':None}]
        v=compute_loss(rows,0);self.assertEqual(v['net_loss_cents'],0)
        self.assertIsNone(v['total_underpaid_cents'])
    def test_reference_tools_exist(self):
        from scripts.a4_fixed_four_check import check_four
        from scripts.a4_evaluate_fixed_evidence import run
        self.assertTrue(callable(check_four));self.assertTrue(callable(run))

if __name__=='__main__':unittest.main()

class A4ProductDefinitionTests(unittest.TestCase):
    def test_product_scope_is_two_distinct_noncommercial_plans(self):
        import json
        from pathlib import Path
        cfg=Path(__file__).resolve().parents[1]/'configs/insurance/research_products_A4_candidate.json'
        spec=json.loads(cfg.read_text(encoding='utf-8'))
        self.assertIs(spec['commercial_quote'],False)
        self.assertEqual({p['product_id'] for p in spec['plans']},{'AgentShield-Core','AgentShield-Plus'})
        for plan in spec['plans']:
            for field in ('deductible_cents','coinsurance_bp','occurrence_limit_cents','annual_aggregate_limit_cents'):
                self.assertIsNone(plan[field], 'No invented binding premium/limit parameter')
        self.assertEqual(spec['premium_method']['commercial_rate_status'],'insufficient_evidence')

