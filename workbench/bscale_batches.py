"""One-at-a-time local launcher for the existing free B-SCALE rule baseline."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import json
import os
from pathlib import Path
import secrets
import threading
from typing import Any, Callable

from sandbox.bscale_authorization import configured_source_path, select_task_ids
from scripts.run_bscale_authorization import run_batch


class BatchAlreadyRunning(RuntimeError):
    pass


class BScaleBatchManager:
    def __init__(self, project_root: Path, *, count: int = 100,
                 on_complete: Callable[[str], None] | None = None,
                 state_path: Path | None = None):
        if not 1 <= count <= 100:
            raise ValueError("B-SCALE browser batch size must be between 1 and 100")
        self.project_root = project_root.resolve()
        self.count = count
        self.on_complete = on_complete
        self.state_path = state_path or (self.project_root / "var/bscale_authorization/current_batch.json")
        self._lock = threading.Lock()
        self._state: dict[str, Any] = self._recover() or self._idle()

    def _idle(self) -> dict[str, Any]:
        return {
            "status": "idle", "batch_id": None, "seed": None,
            "total": self.count, "completed": 0, "normal_refund": 0,
            "manual_review": 0, "failed": 0, "total_refund_cents": 0,
            "selected_task_ids": [], "unique_count": 0,
            "paid_model_calls": 0, "error_code": None,
        }

    def status(self) -> dict[str, Any]:
        with self._lock:
            return deepcopy(self._state)

    def _recover(self) -> dict[str, Any] | None:
        """进程重启后恢复最近一次批次身份（内存态会丢失，曾导致页面把全部历史当“当前批次”混算）。
        只在批次证据目录确实存在运行时恢复；也能把被中断的 running/queued 明确标为 failed。"""
        try:
            if not self.state_path.is_file():
                return None
            saved = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if not isinstance(saved, dict):
            return None
        batch_id = saved.get("batch_id")
        if not isinstance(batch_id, str) or not batch_id.startswith("bscale-web-rule-baseline-"):
            return None
        batch_root = self.project_root / "artifacts/c_l0/runs" / batch_id
        if not batch_root.is_dir() or not any(batch_root.glob("*/manifest.json")):
            return None
        state = self._idle()
        for key in state:
            if key in saved:
                state[key] = saved[key]
        if state["status"] in {"queued", "running"}:
            state["status"] = "failed"
            state["error_code"] = "BATCH_INTERRUPTED"
        if state["status"] not in {"completed", "failed"}:
            return None
        state["batch_id"] = batch_id
        return state

    def _persist(self) -> None:
        # 原子写；失败不影响批次执行，仅丢失重启恢复能力。
        try:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            temp = self.state_path.with_suffix(".json.tmp")
            temp.write_text(json.dumps(self._state, ensure_ascii=False), encoding="utf-8")
            os.replace(temp, self.state_path)
        except OSError:
            pass

    def start(self) -> dict[str, Any]:
        with self._lock:
            if self._state["status"] in {"queued", "running"}:
                raise BatchAlreadyRunning("a B-SCALE batch is already running")
            source = configured_source_path()
            seed = "agentshield-bscale-web-" + secrets.token_hex(16)
            selected = select_task_ids(source, self.count, seed)
            batch_id = "bscale-web-rule-baseline-" + datetime.now().strftime("%Y%m%d-%H%M%S-") + secrets.token_hex(3)
            self._state = {
                **self._idle(), "status": "queued", "batch_id": batch_id,
                "seed": seed, "selected_task_ids": selected,
                "unique_count": len(set(selected)),
            }
            self._persist()
            thread = threading.Thread(
                target=self._run, args=(source, batch_id, seed),
                name="bscale-rule-baseline-batch", daemon=True,
            )
            thread.start()
            return deepcopy(self._state)

    def _progress(self, completed: int, total: int, record: dict[str, Any]) -> None:
        with self._lock:
            self._state["status"] = "running"
            self._state["completed"] = completed
            self._state["total"] = total
            self._state["total_refund_cents"] += record.get("total_committed_cents") or 0
            if record.get("run_status") != "completed":
                self._state["failed"] += 1
            elif record.get("task_outcome") == "completed":
                self._state["normal_refund"] += 1
            elif record.get("task_outcome") == "escalated":
                self._state["manual_review"] += 1
            else:
                self._state["failed"] += 1

    def _run(self, source: Path, batch_id: str, seed: str) -> None:
        with self._lock:
            self._state["status"] = "running"
        try:
            summary = run_batch(
                source, count=self.count, seed=seed,
                summary_path=self.project_root / "var/bscale_authorization" / f"{batch_id}.json",
                batch_id=batch_id, progress_callback=self._progress,
            )
            if self.on_complete is not None:
                self.on_complete(batch_id)
            with self._lock:
                self._state.update({
                    "status": "completed",
                    "completed": summary["selection"]["count"],
                    "normal_refund": summary["execution"]["normal_refund"],
                    "manual_review": summary["execution"]["manual_review"],
                    "failed": summary["execution"]["failed"],
                    "total_refund_cents": summary["execution"]["total_refund_cents"],
                    "paid_model_calls": summary["execution"]["paid_model_calls"],
                })
                self._persist()
        except Exception:
            with self._lock:
                self._state["status"] = "failed"
                self._state["error_code"] = "BATCH_EXECUTION_FAILED"
                self._persist()
