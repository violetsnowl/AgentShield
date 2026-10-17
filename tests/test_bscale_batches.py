"""BScaleBatchManager：状态持久化与重启恢复（防“当前批次”在重启后丢失导致历史混算）。"""
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

import workbench.bscale_batches as batches_module
from workbench.bscale_batches import BatchAlreadyRunning, BScaleBatchManager

ROOT = Path(__file__).resolve().parents[1]
BATCH_ID = "bscale-web-rule-baseline-20261017-000000-abc123"


def write_state(root: Path, payload: dict) -> Path:
    path = root / "var/bscale_authorization/current_batch.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def add_batch_runs(root: Path, batch_id: str, count: int = 2) -> None:
    for index in range(1, count + 1):
        folder = root / "artifacts/c_l0/runs" / batch_id / f"{index:02d}_run"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "manifest.json").write_text("{}", encoding="utf-8")


def state(**overrides) -> dict:
    base = {"status": "completed", "batch_id": BATCH_ID, "seed": "s", "total": 2, "completed": 2,
            "normal_refund": 2, "manual_review": 0, "failed": 0, "total_refund_cents": 500,
            "selected_task_ids": ["rr-synth-00000001", "rr-synth-00000002"], "unique_count": 2,
            "paid_model_calls": 0, "error_code": None}
    base.update(overrides)
    return base


class RecoverPersistTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="bscale-batches-", dir=ROOT / "var")
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_recovers_completed_batch_with_existing_evidence(self):
        write_state(self.root, state())
        add_batch_runs(self.root, BATCH_ID)
        manager = BScaleBatchManager(self.root, count=2)
        status = manager.status()
        self.assertEqual(status["status"], "completed")
        self.assertEqual(status["batch_id"], BATCH_ID)
        self.assertEqual(status["total_refund_cents"], 500)

    def test_phantom_state_without_evidence_is_ignored(self):
        write_state(self.root, state())
        manager = BScaleBatchManager(self.root, count=2)
        self.assertEqual(manager.status()["status"], "idle")
        self.assertIsNone(manager.status()["batch_id"])

    def test_interrupted_running_batch_becomes_failed(self):
        write_state(self.root, state(status="running", completed=1, normal_refund=1))
        add_batch_runs(self.root, BATCH_ID, count=1)
        manager = BScaleBatchManager(self.root, count=2)
        status = manager.status()
        self.assertEqual(status["status"], "failed")
        self.assertEqual(status["error_code"], "BATCH_INTERRUPTED")
        self.assertEqual(status["batch_id"], BATCH_ID)

    def test_foreign_or_invalid_states_rejected(self):
        write_state(self.root, state(batch_id="some-other-batch-2026"))
        self.assertEqual(BScaleBatchManager(self.root, count=2).status()["status"], "idle")
        write_state(self.root, {"note": "garbage"})
        self.assertEqual(BScaleBatchManager(self.root, count=2).status()["status"], "idle")

    def test_start_persists_queued_then_completed(self):
        def fake_run_batch(source, *, count, seed, summary_path, batch_id, progress_callback=None):
            if progress_callback is not None:
                progress_callback(1, count, {"run_status": "completed", "task_outcome": "completed",
                                             "total_committed_cents": 250})
            return {"selection": {"count": count},
                    "execution": {"normal_refund": count, "manual_review": 0, "failed": 0,
                                  "total_refund_cents": 250 * count, "paid_model_calls": 0}}

        with patch.object(batches_module, "configured_source_path", return_value=Path("source.sqlite3")), \
             patch.object(batches_module, "select_task_ids", return_value=["rr-synth-00000001", "rr-synth-00000002"]), \
             patch.object(batches_module, "run_batch", side_effect=fake_run_batch):
            manager = BScaleBatchManager(self.root, count=2)
            started = manager.start()
            self.assertEqual(started["status"], "queued")
            saved = json.loads((self.root / "var/bscale_authorization/current_batch.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["status"], "queued")
            for _ in range(200):
                if manager.status()["status"] not in ("queued", "running"):
                    break
                time.sleep(0.02)
            final = manager.status()
            self.assertEqual(final["status"], "completed")
            self.assertEqual(final["total_refund_cents"], 500)
            saved = json.loads((self.root / "var/bscale_authorization/current_batch.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["status"], "completed")
            self.assertTrue(saved["batch_id"].startswith("bscale-web-rule-baseline-"))

    def test_single_flight_still_enforced(self):
        manager = BScaleBatchManager(self.root, count=2)
        manager._state["status"] = "running"
        with self.assertRaises(BatchAlreadyRunning):
            manager.start()


if __name__ == "__main__":
    unittest.main()
