# -*- coding: utf-8 -*-
"""A-P0 双方案读取边界：C 原始待审格式 与 A7 已研究审核格式（白盒，无证据包依赖）。

- 待审（legacy）格式：coverage 必须仍等于 C 原始输入，且不得包含任何金额。
- A7 已审核格式：coverage=covered/excluded，必须携带研究责任审查记录，且 source 块必须
  与本次 loss_result.json 原始字节哈希 / 证据哈希 / 事前 Gold spec / C 原始口径逐项绑定。
- 金额边界：assessed、非负整数、不超过已核验净损失。
"""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from workbench.integration_results import IntegrationResults  # noqa: E402

EVENT = "episode-session-f476358c221c4609b378ad858472c71b"
CORE_VERSION = "a-p0-core-study-v0.1"
PLUS_VERSION = "a-p0-plus-study-v0.1"
EVIDENCE_SHA = "a8c814f6cbd71412f8be684e0767b0e41e1be844931eb6bdb5cfaa541ae9d6dc"
GOLD_SPEC = "A-AUTOGOLD-rr-synth-00069697-9076afceebcff5f7"


def _loss(status="verified", net=0, coverage="needs_review"):
    return {"loss_status": status, "net_loss_cents": net, "coverage_status_input": coverage,
            "identity": {"evidence_sha256": EVIDENCE_SHA}, "obligation_spec_id": GOLD_SPEC}


def _row(product_id, version, status, coverage, claim_status, payout, retained):
    return {"product_id": product_id, "contract_version": version, "deductible_cents": 10000,
            "coinsurance_bp": 8000, "occurrence_limit_cents": 100000, "annual_aggregate_limit_cents": 10000000,
            "annual_aggregate_calculation_status": "display_only_not_enforced", "event_id": EVENT, "currency": "CNY",
            "net_loss_cents": 0 if status == "verified" else None, "loss_status": status, "coverage_status": coverage,
            "claim_status": claim_status, "payout_cents": payout, "retained_loss_cents": retained, "commercial_quote": False}


def _pending():
    return {"display_schema": "AgentShield.A_P0_claim_comparison.v0.1", "label": "C_saved_loss_result_as_is",
            "source_type": "observed_agent_execution_pending_review", "status": "observed_run_not_formally_admitted",
            "commercial_quote": False, "real_agent_insurance_claim": False, "event_id": EVENT,
            "net_loss_cents": None, "loss_status": "needs_review", "coverage_status": "needs_review",
            "claims": [_row("AgentShield-Core", CORE_VERSION, "needs_review", "needs_review", "needs_review", None, None),
                       _row("AgentShield-Plus", PLUS_VERSION, "needs_review", "needs_review", "needs_review", None, None)],
            "notes": []}


def _reviewed(loss_sha):
    return {"display_schema": "AgentShield.A_P0_claim_comparison.v0.1",
            "label": "C_REAL_DEEPSEEK_A_COVERAGE_REVIEWED_ZERO_LOSS",
            "source_type": "observed_agent_execution_pending_review",
            "status": "A_study_reviewed_zero_loss_not_formal_insurance_claim",
            "commercial_quote": False, "real_agent_insurance_claim": False, "event_id": EVENT,
            "net_loss_cents": 0, "loss_status": "verified", "coverage_status": "covered",
            "A_study_coverage_review": {"review_version": "A7-insurance-coverage-review-v0.1",
                                        "coverage_scope_status": "covered", "covered_loss_triggered": False,
                                        "formal_claim_adjudication": False},
            "source": {"run_type": "observed_DeepSeek_development_execution", "episode_id": EVENT,
                       "config_id": "c-deepseek-flash-fixed-dev-v0.1", "evidence_sha256": EVIDENCE_SHA,
                       "C_loss_result_sha256": loss_sha, "obligation_spec_id": GOLD_SPEC,
                       "C_verified_net_loss_cents": 0, "C_original_coverage_status": "needs_review"},
            "claims": [_row("AgentShield-Core", CORE_VERSION, "verified", "covered", "assessed", 0, 0),
                       _row("AgentShield-Plus", PLUS_VERSION, "verified", "covered", "assessed", 0, 0)],
            "notes": []}


class P0ClaimReadingBoundary(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "runs").mkdir()
        self.results = IntegrationResults(self.root / "runs", ROOT)
        self.folder = self.root / "batch" / "case"
        self.folder.mkdir(parents=True)
        self.loss_bytes = b'{"stub": "loss-result"}\n'
        (self.folder / "loss_result.json").write_bytes(self.loss_bytes)
        self.loss_sha = hashlib.sha256(self.loss_bytes).hexdigest()

    def tearDown(self):
        self._tmp.cleanup()

    def _load(self, claim, loss):
        (self.folder / "claim_core_plus.json").write_text(json.dumps(claim, ensure_ascii=False), encoding="utf-8")
        return self.results._load_p0_claims(self.folder / "claim_core_plus.json", "batch/case", loss, EVENT)

    def test_missing_file_is_none(self):
        self.assertIsNone(self.results._load_p0_claims(self.folder / "nope.json", "batch/case", _loss(), EVENT))

    def test_legacy_pending_claims_still_accepted(self):
        p0 = self._load(_pending(), _loss("needs_review", None))
        self.assertEqual(p0["coverage_status"], "needs_review")
        self.assertEqual([row["payout_cents"] for row in p0["claims"]], [None, None])

    def test_pending_claims_must_keep_c_coverage(self):
        claim = _pending()
        claim["coverage_status"] = "covered"
        with self.assertRaisesRegex(ValueError, "pending result must keep C coverage input"):
            self._load(claim, _loss("needs_review", None))

    def test_a7_reviewed_zero_claims_accepted(self):
        p0 = self._load(_reviewed(self.loss_sha), _loss())
        self.assertEqual([row["payout_cents"] for row in p0["claims"]], [0, 0])
        self.assertEqual(p0["coverage_status"], "covered")
        self.assertEqual(p0["A_study_coverage_review"]["review_version"], "A7-insurance-coverage-review-v0.1")

    def test_a7_requires_review_record(self):
        claim = _reviewed(self.loss_sha)
        del claim["A_study_coverage_review"]
        with self.assertRaisesRegex(ValueError, "review record"):
            self._load(claim, _loss())

    def test_a7_review_record_must_match_stated_coverage(self):
        claim = _reviewed(self.loss_sha)
        claim["A_study_coverage_review"]["coverage_scope_status"] = "excluded"
        with self.assertRaisesRegex(ValueError, "review record"):
            self._load(claim, _loss())

    def test_a7_requires_loss_result_sha_binding(self):
        with self.assertRaisesRegex(ValueError, "source binding"):
            self._load(_reviewed("0" * 64), _loss())

    def test_a7_requires_verified_loss(self):
        # 未核验损失（net 为 null）与 A7 已审核声明（net=0）必然先被身份守卫拒绝：
        # A7 研究审核只允许落在 verified 损失之上。
        with self.assertRaisesRegex(ValueError, "identity or status mismatch"):
            self._load(_reviewed(self.loss_sha), _loss("needs_review", None))

    def test_a7_claim_money_must_be_bounded(self):
        claim = _reviewed(self.loss_sha)
        claim["claims"][0]["payout_cents"] = 100
        with self.assertRaisesRegex(ValueError, "bounded"):
            self._load(claim, _loss())

    def test_unknown_status_rejected(self):
        claim = _reviewed(self.loss_sha)
        claim["status"] = "something_else"
        with self.assertRaisesRegex(ValueError, "unknown A-P0 review status"):
            self._load(claim, _loss())

    def test_real_a7_delivery_parses(self):
        run = ROOT / "artifacts/c_l0/runs/bscale-web-deepseek-20261017-155329-8f3a21/01_bscale_sim_rr_synth_00069697"
        if not (run / "claim_core_plus.json").is_file():
            self.skipTest("real A7 delivery not staged")
        loss = json.loads((run / "loss_result.json").read_text(encoding="utf-8"))
        p0 = self.results._load_p0_claims(run / "claim_core_plus.json", "real", loss, loss["identity"]["episode_id"])
        self.assertEqual([row["payout_cents"] for row in p0["claims"]], [0, 0])
        self.assertEqual(p0["status"], "A_study_reviewed_zero_loss_not_formal_insurance_claim")


if __name__ == "__main__":
    unittest.main()
