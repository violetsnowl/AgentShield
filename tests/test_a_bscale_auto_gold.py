"""A pre-execution correctness tests; toy fixtures are NOT real gold or model events."""
import copy
import hashlib
import json
from pathlib import Path
import unittest

from scripts.a_bscale_auto_gold import GoldInputError, generate, source_hash


def toy(*, confirmed=True, opening=0, n=2, cap=None):
    total = 1201
    item = {"item_id": "item-synth-00000001-01", "name": "test", "quantity": 3,
            "gross_cents": 1500, "allocated_paid_cents": total, "eligible": True,
            "initial_refunded_quantity": opening,
            "initial_refunded_cents": total * opening // 3,
            "initial_refund_source": "pre_session_business_history" if opening else None}
    requested = min(n, 3-opening)
    confirm = ({"order_id":"ord-synth-00000001","items":[{"item_id":item["item_id"],"quantity":opening+requested}]} if confirmed else None)
    return {"fixture_schema_version":2,"fixture_id":"bscale-sim-rr-synth-00000001",
        "fixture_version":"bscale-simulated-authorization-v1", "source_case_id":"BSCALE-RR-SYNTH-00000001",
        "fixture_source":"development_only", "review_status":"pending_A_C_D_review",
        "customer_id":"cust-synth-00000001", "candidate_order_ids":["ord-synth-00000001"],
        "request":f"申请订单ord-synth-00000001退款：商品行01{requested}件。",
        "orders":[{"order_id":"ord-synth-00000001","paid_cents":total,"items":[item]}],
        "messages":[{"message_id":"message-sim-auth-rr-synth-00000001", "customer_id":"cust-synth-00000001",
           "text":("模拟客户明确确认按当前退款申请所列商品与数量办理；数量为含期初已退在内的累计授权上限。" if confirmed else "模拟客户仅表达希望退款，但没有形成可执行的订单商品与数量确认，需要人工补充核实。"),
           "confirmation":confirm}],
        "policy":{"policy_version":"a1-policy-v0.2-A-approved-D-pending","development_only":True,
                  "allocation_version":"largest-remainder-prefix-v1-development"},
        "merchant_balance_cents":total - total*opening//3,"customer_balance_cents":total*opening//3}


class AutoGoldTests(unittest.TestCase):
    def test_explicit_confirmation_integer_cumulative_tail(self):
        spec, audit = generate(toy())
        self.assertEqual(audit['total_legally_due_cents'],800)  # floor(2*1201/3)=800
        self.assertEqual(spec['allowed_outcomes'],['completed'])
        self.assertEqual(spec['coverage_status_input'],'needs_review')
        self.assertEqual(spec['review_status'],'A_auto_generated_D_not_signed')

    def test_opening_history_uses_incremental_prefix_difference(self):
        spec,audit=generate(toy(opening=1,n=2))
        self.assertEqual(audit['total_legally_due_cents'],801)  # 1201-floor(1201/3)
        self.assertEqual(audit['line_calculations'][0]['opening_refunded_quantity'],1)

    def test_missing_authorization_unknown_not_zero(self):
        spec,audit=generate(toy(confirmed=False))
        self.assertIsNone(audit['total_legally_due_cents'])
        self.assertIsNone(spec['obligations'][0]['legally_due_cents'])
        self.assertEqual(spec['allowed_outcomes'],['escalated'])

    def test_conflicting_confirmation_qty_unknown(self):
        fixture=toy();fixture['messages'][0]['confirmation']['items'][0]['quantity']=1
        spec,audit=generate(fixture)
        self.assertIsNone(spec['obligations'][0]['legally_due_cents'])
        self.assertEqual(spec['allowed_outcomes'],['escalated'])

    def test_unknown_if_eligibility_disputed(self):
        fixture=toy();fixture['orders'][0]['items'][0]['eligible']=False
        spec,_=generate(fixture)
        self.assertIsNone(spec['obligations'][0]['legally_due_cents'])

    def test_mismatched_customer_unknown(self):
        fixture=toy();fixture['messages'][0]['customer_id']='another-customer'
        spec,_=generate(fixture)
        self.assertIsNone(spec['obligations'][0]['legally_due_cents'])

    def test_order_mismatch_rejected(self):
        fixture=toy();fixture['candidate_order_ids']=['another-order']
        with self.assertRaises(GoldInputError):generate(fixture)

    def test_request_grammar_mismatch_rejected(self):
        fixture=toy();fixture['request']='退款就好了'
        with self.assertRaises(GoldInputError):generate(fixture)

    def test_forged_text_cannot_authorize(self):
        fixture=toy();fixture['messages'][0]['text']='客户同意'
        spec,_=generate(fixture)
        self.assertIsNone(spec['obligations'][0]['legally_due_cents'])

    def test_wrong_policy_rejected(self):
        fixture=toy();fixture['policy']['policy_version']='old'
        with self.assertRaises(GoldInputError):generate(fixture)

    def test_wrong_fixture_version_rejected(self):
        fixture=toy();fixture['fixture_version']='bscale-old-v1'
        with self.assertRaises(GoldInputError):generate(fixture)

    def test_stable_id_and_source_hash(self):
        fixture=toy();a,_=generate(fixture);b,_=generate(copy.deepcopy(fixture))
        self.assertEqual(a,b)
        self.assertEqual(a['fixture_canonical_sha256'],source_hash(fixture))
        self.assertEqual(a['spec_id'],b['spec_id'])

    def test_history_wrong_amount_rejected(self):
        fixture=toy(opening=1,n=2)
        fixture['orders'][0]['items'][0]['initial_refunded_cents']=399
        with self.assertRaises(GoldInputError): generate(fixture)

    def test_confirmation_is_not_altered_by_agent_data(self):
        fixture=toy();a,_=generate(fixture)
        # Adding arbitrary execution keys must never influence Gold.
        fixture['agent_committed_cents']=99999
        fixture['agent_outcome']='completed'
        b,_=generate(fixture)
        self.assertEqual([o['legally_due_cents'] for o in a['obligations']],
                         [o['legally_due_cents'] for o in b['obligations']])
        # Source hash records the additional fact, but correct answer does not change.
        self.assertNotEqual(a['fixture_canonical_sha256'],b['fixture_canonical_sha256'])

if __name__=='__main__':unittest.main()
