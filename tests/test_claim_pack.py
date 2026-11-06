"""Claim packs must rebuild their amounts from evidence and refuse anything that does not add up."""
import gzip
import hashlib
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from evaluator.obligations import SpecError
from experiments import claim_pack
from experiments.claim_pack import ClaimPackError, build_pack, conclusion, render_html, verify_pack, write_pack, yuan
from experiments.reverify_evidence import apply_obligation
from runners.adapters import RedTeamAdapter
from runners.attempts import AttemptLog
from runners.loop import Budget, Pricing, run_episode
from runners.tools import model_tool_specs
from sandbox.risk_tasks_hard import select_hard_tasks
from scripts.a_risk_gold import generate
from tests.test_risk_experiment import ADMIN, FakeSession, RiskExperimentBase

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = json.loads((ROOT / "configs/insurance/research_contract_v0.1.json").read_text(encoding="utf-8"))


class ClaimPackBase(RiskExperimentBase):
    def reckless_run(self, profile="P0"):
        """First hard task the reckless Agent loses money on, with its evidence as exported."""
        for fixture_id in select_hard_tasks(self.source, 1):
            created = self.create(fixture_id, profile)
            log = AttemptLog(self.root / f"{profile}-{fixture_id}.jsonl")
            run_episode(RedTeamAdapter(), FakeSession(self.client, created), log, system_prompt="-", kickoff="-",
                        tool_specs=model_tool_specs(profile), budget=Budget(max_turns=200, max_tool_calls=400),
                        pricing=Pricing(), run_tag="pack")
            response = self.client.get(f"/api/v1/admin/sessions/{created['session']['session_id']}/evidence",
                                       headers={"Authorization": "Bearer " + ADMIN})
            evidence = response.json()
            raw = json.dumps(evidence, ensure_ascii=False, sort_keys=True).encode("utf-8")
            spec = generate(fixture_id, self.source)
            pack = build_pack(evidence, spec, CONTRACT, evidence_sha256=hashlib.sha256(raw).hexdigest(),
                              run={"family": fixture_id.split("-")[2], "model": "red-team"})
            if pack["summary"]["net_loss_cents"] > 0:
                return evidence, raw, spec, pack
        self.fail("reckless Agent lost nothing on any hard task")


class ClaimPackTests(ClaimPackBase):
    def test_amounts_follow_the_contract_step_by_step(self):
        _, _, _, pack = self.reckless_run()
        summary, steps = pack["summary"], pack["indemnity"]
        net = summary["net_loss_cents"]
        self.assertEqual(net, summary["extra_cents"] - summary["recovery_cents"])
        self.assertEqual(steps["eligible_cents"], max(net - CONTRACT["deductible_cents"], 0))
        self.assertEqual(summary["payout_cents"], min(steps["share_cents"], CONTRACT["occurrence_limit_cents"], net))
        self.assertEqual(summary["payout_cents"] + summary["retained_loss_cents"], net)
        self.assertEqual(sum(row["extra_cents"] for row in pack["lines"]), summary["extra_cents"])

    def test_page_is_readable_chinese_and_says_what_it_is_not(self):
        _, _, _, pack = self.reckless_run()
        page = render_html(pack)
        for words in ("事故经过", "逐行核对", "账本核对", "净损失计算", "保险责任与赔款", "第二十二条", "不是真实客户的损失"):
            self.assertIn(words, page)
        for jargon in ("needs_review", "net_loss_cents", "submit_refund", "null"):
            self.assertNotIn(jargon, page)
        self.assertFalse(pack["commercial_quote"])

    def test_text_from_the_run_cannot_inject_markup(self):
        _, _, _, pack = self.reckless_run()
        pack["case"]["agent_explanation"] = "<script>alert(1)</script>"
        page = render_html(pack)
        self.assertNotIn("<script>", page)
        self.assertIn("&lt;script&gt;", page)

    def test_a_stored_result_that_disagrees_stops_the_export(self):
        evidence, raw, spec, pack = self.reckless_run()
        stored = {key: pack["loss_result"][key] for key in ("net_loss_cents", "total_extra_cents", "total_committed_cents", "loss_status")}
        build_pack(evidence, spec, CONTRACT, evidence_sha256="x", stored_loss=stored)
        with self.assertRaisesRegex(ClaimPackError, "net_loss_cents"):
            build_pack(evidence, spec, CONTRACT, evidence_sha256="x", stored_loss={**stored, "net_loss_cents": 1})

    def test_unknown_money_is_never_shown_as_zero(self):
        self.assertEqual(yuan(None), "未知")
        self.assertEqual(yuan(5), "¥0.05")
        self.assertEqual(yuan(123456789), "¥1,234,567.89")
        base = {"summary": {"loss_status": "needs_review", "net_loss_cents": None, "payout_cents": None,
                            "claim_status": "needs_review", "retained_loss_cents": None}}
        self.assertIn("尚未核验", conclusion(base))

    def test_conclusion_separates_the_ways_a_claim_pays_nothing(self):
        def line(net, payout, status, retained=None):
            return conclusion({"summary": {"loss_status": "verified", "net_loss_cents": net, "payout_cents": payout,
                                           "claim_status": status, "retained_loss_cents": retained}})
        self.assertIn("无需赔付", line(0, 0, "assessed", 0))
        self.assertIn("低于免赔额", line(2644, 0, "assessed", 2644))
        self.assertIn("待人工认定", line(5000, None, "needs_review"))
        self.assertIn("除外责任", line(5000, 0, "not_covered", 5000))
        self.assertIn("¥1,000.00", line(436306, 100000, "assessed", 336306))

    def test_a_coverage_question_stays_open(self):
        evidence, raw, spec, _ = self.reckless_run()
        pack = build_pack(evidence, {**spec, "coverage_status_input": "needs_review"}, CONTRACT, evidence_sha256="x")
        self.assertIsNone(pack["summary"]["payout_cents"])
        self.assertTrue(any("待人工认定" in item for item in pack["open_items"]))
        self.assertIn("暂不给出", render_html(pack))


class ClaimPackFileTests(ClaimPackBase):
    def exported(self):
        _, raw, _, pack = self.reckless_run()
        target = self.root / "pack"
        write_pack(pack, raw, target)
        return target

    def test_a_fresh_pack_verifies(self):
        self.assertEqual(verify_pack(self.exported()), [])

    def test_editing_any_file_is_detected(self):
        target = self.exported()
        for name in ("evidence.json", "claim_pack.json", "理赔材料.html"):
            path = target / name
            original = path.read_bytes()
            path.write_bytes(original + b" ")
            self.assertTrue(any(name in problem for problem in verify_pack(target)), name)
            path.write_bytes(original)
        self.assertEqual(verify_pack(target), [])

    def test_changing_an_amount_and_refreshing_the_digest_is_still_caught(self):
        target = self.exported()
        path = target / "claim_pack.json"
        pack = json.loads(path.read_text(encoding="utf-8"))
        pack["summary"]["payout_cents"] += 100
        pack["summary"]["net_loss_cents"] += 100
        data = json.dumps(pack, ensure_ascii=False).encode("utf-8")
        path.write_bytes(data)
        manifest = json.loads((target / "manifest.json").read_text(encoding="utf-8"))
        manifest["files"]["claim_pack.json"] = hashlib.sha256(data).hexdigest()
        (target / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        problems = verify_pack(target)
        self.assertIn("净损失无法由逐行金额重新算出", problems)
        self.assertIn("赔款无法由合同条款重新算出", problems)

    def test_evidence_that_differs_from_the_batch_record_is_refused(self):
        with tempfile.TemporaryDirectory(dir=self.root) as folder:
            raw_root = Path(folder)
            row = {"control_profile": "P0", "fixture_id": "f", "attempt": 1, "evidence_sha256": "0" * 64}
            run_dir = raw_root / "batch" / "P0_f_a1"
            run_dir.mkdir(parents=True)
            (run_dir / "evidence.json.gz").write_bytes(gzip.compress(b"{}"))
            (run_dir / "loss_result.json.gz").write_bytes(gzip.compress(b"{}"))
            with self.assertRaisesRegex(ClaimPackError, "digest differs"):
                claim_pack.read_run("batch", row, raw_root)
            with self.assertRaisesRegex(ClaimPackError, "not on this machine"):
                claim_pack.read_run("other", row, raw_root)

    def test_only_completed_runs_at_or_above_the_floor_are_accidents(self):
        self.assertTrue(claim_pack.is_accident({"run_status": "completed", "net_loss_cents": 100}))
        self.assertFalse(claim_pack.is_accident({"run_status": "completed", "net_loss_cents": 99}))
        self.assertFalse(claim_pack.is_accident({"run_status": "infra_error", "net_loss_cents": 63470}))
        self.assertFalse(claim_pack.is_accident({"run_status": "completed", "net_loss_cents": None}))

    def test_only_the_latest_attempt_of_a_cell_counts(self):
        batch = self.root / "results" / "batch"
        batch.mkdir(parents=True)
        rows = [{"fixture_id": "f", "control_profile": "P0", "attempt": 1, "run_status": "infra_error"},
                {"fixture_id": "f", "control_profile": "P0", "attempt": 2, "run_status": "completed"}]
        (batch / "results.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
        with patch.object(claim_pack, "RESULTS_ROOT", self.root / "results"):
            latest = claim_pack.latest_rows("batch", self.root / "results")
        self.assertEqual([row["attempt"] for row in latest], [2])


class ApplyObligationTests(ClaimPackBase):
    def saved_run(self):
        evidence, raw, spec, pack = self.reckless_run()
        run_dir = self.root / "run"
        run_dir.mkdir()
        (run_dir / "evidence.json").write_bytes(raw)
        (run_dir / "loss_result.json").write_text('{"before": true}', encoding="utf-8")
        (run_dir / "claim_A0.json").write_text('{"before": true}', encoding="utf-8")
        return run_dir, spec, pack

    def test_the_result_from_before_the_spec_is_kept_and_never_overwritten(self):
        run_dir, spec, pack = self.saved_run()
        loss, claim = apply_obligation(run_dir, spec, CONTRACT)
        self.assertEqual(loss["net_loss_cents"], pack["summary"]["net_loss_cents"])
        self.assertEqual(claim["payout_cents"], pack["summary"]["payout_cents"])
        apply_obligation(run_dir, spec, CONTRACT)
        self.assertEqual(json.loads((run_dir / "loss_result_before_gold.json").read_text(encoding="utf-8")), {"before": True})
        self.assertEqual(json.loads((run_dir / "loss_result.json").read_text(encoding="utf-8"))["net_loss_cents"], loss["net_loss_cents"])
        self.assertTrue((run_dir / "post_obligation" / "claim_A0.json").is_file())

    def test_a_malformed_spec_changes_nothing(self):
        run_dir, spec, _ = self.saved_run()
        with self.assertRaises(SpecError):
            apply_obligation(run_dir, {**spec, "coverage_status_input": "maybe"}, CONTRACT)
        self.assertEqual(json.loads((run_dir / "loss_result.json").read_text(encoding="utf-8")), {"before": True})
        self.assertFalse((run_dir / "loss_result_before_gold.json").exists())
