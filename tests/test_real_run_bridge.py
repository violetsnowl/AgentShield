# -*- coding: utf-8 -*-
"""真实运行桥接：计划过门、付费批准边界、Gold 目录隔离、管理器状态机与免费 dry-run 全链路。"""
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import scripts.run_real_batch as bridge  # noqa: E402
from experiments.formal_gates import dev_launch_block  # noqa: E402
from workbench.real_runs import (RealRunAlreadyRunning, RealRunManager,  # noqa: E402
                                 RealRunNotAuthorized)


def find_source_db() -> Path | None:
    candidates = [os.environ.get("AGENTSHIELD_BSCALE_DB")]
    sibling = ROOT.parent / "AgentShield_BSCALE_Source_20261017" / "synthetic_merchant_v1.sqlite3"
    candidates.append(str(sibling))
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return Path(candidate)
    return None


SOURCE_DB = find_source_db()


class PlanAndGateTests(unittest.TestCase):
    def test_plan_shape_passes_dev_gate(self):
        plan = bridge.build_plan("bscale-web-dryrun", "exp-1", "configs/runner/rule-baseline-v0.1.json",
                                 ["rr-synth-00069697", "rr-synth-00000007"])
        self.assertIsNone(dev_launch_block(plan))
        self.assertFalse(plan["launch_paid_api"])
        self.assertFalse(plan["counts_as_formal_run"])
        self.assertEqual(plan["runs"][0]["fixture_id"], "bscale-sim-rr-synth-00069697")
        self.assertEqual(plan["runs"][0]["label"], "bscale_sim_rr_synth_00069697")

    def test_requested_cap_mapping(self):
        self.assertEqual(bridge.requested_cap(1), 0.5)
        self.assertEqual(bridge.requested_cap(5), 1.5)
        self.assertEqual(bridge.requested_cap(2), 1.0)

    def test_incremental_process_cap_deducts_prior_ledger(self):
        # 本轮新增 ¥1.50 + 既有台账 ¥0.136644 → 进程硬顶 ¥1.636644（剩余恰为新增额度）
        self.assertEqual(bridge.process_cap_for(1.5, 0.136644), 1.636644)
        self.assertEqual(bridge.process_cap_for(0.5, 0.0), 0.5)

    def test_paid_gate_requires_approval_cap_and_key(self):
        with self.assertRaisesRegex(bridge.RealBatchError, "budget approval"):
            bridge.authorize_paid(0.5, None, {"DEEPSEEK_API_KEY": "x"})
        with self.assertRaisesRegex(bridge.RealBatchError, "exceeds approved"):
            bridge.authorize_paid(0.5, 0.25, {"DEEPSEEK_API_KEY": "x"})
        with self.assertRaisesRegex(bridge.RealBatchError, "DEEPSEEK_API_KEY"):
            bridge.authorize_paid(0.5, 0.5, {})
        with self.assertRaisesRegex(bridge.RealBatchError, "positive process cap"):
            bridge.authorize_paid(None, 0.5, {"DEEPSEEK_API_KEY": "x"})
        self.assertEqual(bridge.authorize_paid(0.5, 0.5, {"DEEPSEEK_API_KEY": "x"}), 0.5)

    def test_gold_dir_must_be_outside_git_working_tree(self):
        with self.assertRaisesRegex(bridge.RealBatchError, "outside the Git"):
            bridge.ensure_private_dir(ROOT / "artifacts" / "should-not-be-here")
        with tempfile.TemporaryDirectory() as temp:
            self.assertEqual(bridge.ensure_private_dir(Path(temp)), Path(temp).resolve())


class ManagerTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        (self.tmp / "project/var/real_run").mkdir(parents=True)
        (self.tmp / "project/artifacts/c_l0/runs").mkdir(parents=True)
        self.project = self.tmp / "project"
        self.gold = self.tmp / "gold"

    def tearDown(self):
        self._tmp.cleanup()

    def _manager(self, *, approval=None, env=None, source=SOURCE_DB):
        approval_path = self.tmp / "approval.json"
        if approval is not None:
            approval_path.write_text(json.dumps({"active_cap_cny": approval}), encoding="utf-8")
        return RealRunManager(self.project, state_path=self.tmp / "state.json", approval_path=approval_path,
                              gold_root=self.gold, source_db=source, env_loader=lambda: dict(env or {}))

    def test_start_refused_without_key_and_approval(self):
        source = self.tmp / "db.sqlite3"
        source.write_bytes(b"")
        manager = self._manager(env={}, source=source)
        with self.assertRaises(RealRunNotAuthorized) as caught:
            manager.start(1)
        self.assertTrue(any("DEEPSEEK_API_KEY" in reason for reason in caught.exception.reasons))
        self.assertTrue(any("未授权" in reason for reason in caught.exception.reasons))
        with self.assertRaisesRegex(RealRunNotAuthorized, "超出已批"):
            self._manager(approval=0.25, env={"DEEPSEEK_API_KEY": "x"}, source=source).start(1)

    def test_authorization_reports_caps_and_prior_paid(self):
        ledger = self.project / "artifacts/c_l0/cost_ledger.jsonl"
        ledger.write_text(json.dumps({"cost_cny": 0.026}) + "\n" + json.dumps({"cost_cny": 0.021}) + "\n", encoding="utf-8")
        manager = self._manager(approval=0.5, env={"DEEPSEEK_API_KEY": "x"}, source=self.tmp)
        auth = manager.authorization()
        self.assertTrue(auth["has_key"] and auth["approval_cap_cny"] == 0.5)
        self.assertAlmostEqual(auth["prior_paid_cny"], 0.047, places=6)
        self.assertNotIn("DEEPSEEK_API_KEY", json.dumps(auth))

    def test_recover_marks_interrupted_and_restores_completed(self):
        (self.tmp / "state.json").write_text(json.dumps({"status": "running", "batch_id": "bscale-web-deepseek-x"}),
                                             encoding="utf-8")
        manager = self._manager(approval=0.5, env={"DEEPSEEK_API_KEY": "x"}, source=self.tmp)
        self.assertEqual(manager.status()["status"], "failed")
        self.assertEqual(manager.status()["error_code"], "REAL_BATCH_INTERRUPTED")
        batch = self.project / "artifacts/c_l0/runs/bscale-web-deepseek-done-1"
        (batch / "01_x").mkdir(parents=True)
        (batch / "01_x/manifest.json").write_text("{}", encoding="utf-8")
        (self.tmp / "state.json").write_text(json.dumps({"status": "completed", "batch_id": "bscale-web-deepseek-done-1",
                                                         "count": 1, "runs": []}), encoding="utf-8")
        manager = self._manager(approval=0.5, env={"DEEPSEEK_API_KEY": "x"}, source=self.tmp)
        self.assertEqual(manager.status()["status"], "completed")
        self.assertEqual(manager.status()["batch_id"], "bscale-web-deepseek-done-1")

    def test_single_flight(self):
        manager = self._manager(approval=0.5, env={"DEEPSEEK_API_KEY": "x"}, source=self.tmp)
        manager._state["status"] = "running"
        with self.assertRaises(RealRunAlreadyRunning):
            manager.start(1)

    def test_start_returns_promptly_without_lock_deadlock(self):
        # 回归：start() 曾在持锁时调用 status()（非可重入锁）导致端点死锁。
        import time
        source = self.tmp / "db2.sqlite3"
        source.write_bytes(b"")
        stub = self.tmp / "stub_orchestrator.py"
        (self.tmp / "approval2.json").write_text(json.dumps({"active_cap_cny": 0.5}), encoding="utf-8")
        stub.write_text(
            "import json, pathlib, sys\n"
            "args = sys.argv\n"
            "status = pathlib.Path(args[args.index('--status') + 1])\n"
            "status.write_text(json.dumps({'stage': 'completed', 'batch_id': 'bscale-web-deepseek-stub',"
            " 'runs': []}), encoding='utf-8')\n",
            encoding="utf-8")
        manager = RealRunManager(self.project, state_path=self.tmp / "state2.json",
                                 approval_path=self.tmp / "approval2.json", gold_root=self.gold,
                                 source_db=source, env_loader=lambda: {"DEEPSEEK_API_KEY": "x"},
                                 orchestrator=stub)
        started = manager.start(1)
        self.assertIn(started["status"], ("queued", "running", "completed"))
        deadline = time.time() + 10
        while time.time() < deadline and manager.status()["status"] != "completed":
            time.sleep(0.2)
        self.assertEqual(manager.status()["status"], "completed")
        self.assertEqual(manager.status()["batch_id"], "bscale-web-deepseek-stub")


@unittest.skipIf(SOURCE_DB is None, "B-SCALE source database not staged on this machine")
class FreeDryRunEndToEnd(unittest.TestCase):
    def test_rule_baseline_chain_produces_final_files(self):
        with tempfile.TemporaryDirectory() as temp:
            tmp = Path(temp)
            status_path = tmp / "status.json"
            code = bridge.main(["--count", "1", "--seed", "agentshield-test-bridge-e2e",
                                "--prefix", "bscale-web-dryrun-test",
                                "--config", "configs/runner/rule-baseline-v0.1.json",
                                "--status", str(status_path), "--work-dir", str(tmp / "work"),
                                "--gold-dir", str(tmp / "gold"), "--source-db", str(SOURCE_DB)])
            status = json.loads(status_path.read_text(encoding="utf-8"))
            batch_id = status.get("batch_id")
            batch_dir = ROOT / "artifacts/c_l0/runs" / batch_id if batch_id else None
            try:
                self.assertEqual(code, 0, status.get("error"))
                self.assertEqual(status["stage"], "completed")
                self.assertEqual(status["count"], 1)
                self.assertEqual(len(status["runs"]), 1)
                run_dir = batch_dir / status["runs"][0]["label"]
                for name in ("manifest.json", "evidence.json", "loss_result.json", "claim_A0.json",
                             "loss_result_before_gold.json", "claim_A0_before_gold.json",
                             "post_obligation/loss_result.json"):
                    self.assertTrue((run_dir / name).is_file(), name)
                loss = json.loads((run_dir / "loss_result.json").read_text(encoding="utf-8"))
                self.assertIn(loss["loss_status"], ("verified", "needs_review"))
                spec_files = list((tmp / "gold" / batch_id).glob("obligation_*.json"))
                self.assertEqual(len(spec_files), 1)
                from workbench.integration_results import IntegrationResults
                reader = IntegrationResults(ROOT / "artifacts/c_l0/runs", ROOT)
                rows = [row for row in reader.catalog()["runs"] if row["batch_id"] == batch_id]
                self.assertEqual(len(rows), 1)
            finally:
                if batch_dir is not None:
                    shutil.rmtree(batch_dir, ignore_errors=True)
                var_batch = ROOT / "var/c_runs" / str(batch_id)
                shutil.rmtree(var_batch, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
