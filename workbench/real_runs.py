# -*- coding: utf-8 -*-
"""真实 DeepSeek 批次的网页管理器：单飞、持久化、重启恢复、授权与预算探测。

只编排 scripts/run_real_batch.py 子进程；不直接调用模型、不读密钥内容（只判断存在性）。
付费启用与上限由编排器在子进程内注入；本模块绝不把密钥值写入状态或响应。
"""
from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import threading
import time
from typing import Any, Callable

from runners.env import load_runner_env, paid_authorization

PER_RUN_CAP_CNY = 0.5
STAGE_CAPS = {1: 0.5, 5: 1.5}
DEFAULT_PREFIX = "bscale-web-deepseek"
COST_LEDGER = "artifacts/c_l0/cost_ledger.jsonl"


class RealRunAlreadyRunning(RuntimeError):
    pass


class RealRunNotAuthorized(RuntimeError):
    def __init__(self, reasons: list[str]):
        self.reasons = list(reasons)
        super().__init__("; ".join(self.reasons))


class RealRunManager:
    def __init__(self, project_root: Path, *, on_complete: Callable[[str], None] | None = None,
                 state_path: Path | None = None, approval_path: Path | None = None,
                 gold_root: Path | None = None, source_db: Path | None = None,
                 env_loader: Callable[[], dict[str, str]] = load_runner_env,
                 orchestrator: Path | None = None):
        self.project_root = project_root.resolve()
        self.on_complete = on_complete
        self.state_path = state_path or (self.project_root / "var/real_run/current_batch.json")
        self.approval_path = approval_path or (self.project_root / "var/real_run/approval.json")
        self.gold_root = gold_root or (self.project_root.parent / "AgentShield_RealGold")
        self.source_db = source_db
        self.env_loader = env_loader
        self.orchestrator = orchestrator or (self.project_root / "scripts/run_real_batch.py")
        self._var_dir = self.project_root / "var/real_run"
        self._live_path = self._var_dir / "live_status.json"
        self._lock = threading.Lock()
        self._state: dict[str, Any] = self._recover() or self._idle()
        self._process: subprocess.Popen[str] | None = None

    def _idle(self) -> dict[str, Any]:
        return {"status": "idle", "batch_id": None, "count": None, "seed": None, "stage": None,
                "runs": [], "batch_dir": None, "error_code": None, "error": None,
                "paid": True, "cap_cny": None}

    # ── 授权与预算探测（绝不回显密钥值） ─────────────────────────────────────────
    def _source(self) -> Path | None:
        candidates: list[Any] = [self.source_db, os.environ.get("AGENTSHIELD_BSCALE_DB")]
        try:
            config = self.project_root / "var/real_run/config.json"
            if config.is_file():
                candidates.append(json.loads(config.read_text(encoding="utf-8")).get("source_db"))
        except (OSError, ValueError):
            pass
        for candidate in candidates:
            if candidate:
                path = Path(candidate)
                if path.is_file():
                    return path.resolve()
        return None

    def _approval(self) -> float | None:
        try:
            value = json.loads(self.approval_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        cap = value.get("active_cap_cny")
        if type(cap) not in (int, float) or cap <= 0:
            return None
        return float(cap)

    def _prior_paid(self) -> tuple[float, bool]:
        ledger = self.project_root / COST_LEDGER
        if not ledger.is_file():
            return 0.0, True
        total, known = 0.0, True
        for line in ledger.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except ValueError:
                known = False
                continue
            if row.get("cost_cny") is None:
                known = False
            else:
                total += float(row["cost_cny"])
        return round(total, 6), known

    def authorization(self) -> dict[str, Any]:
        values = self.env_loader()
        allowed, _cap, reason = paid_authorization(values)
        prior_total, prior_known = self._prior_paid()
        return {
            "paid_enabled": allowed,
            "paid_reason": None if allowed else reason,
            "has_key": bool(values.get("DEEPSEEK_API_KEY")),
            "approval_cap_cny": self._approval(),
            "prior_paid_cny": prior_total,
            "prior_paid_known": prior_known,
            "source_available": self._source() is not None,
            "per_run_cap_cny": PER_RUN_CAP_CNY,
            "stage_caps": {str(key): value for key, value in STAGE_CAPS.items()},
            "allowed_counts": sorted(STAGE_CAPS),
            "count_limit": 10,
        }

    # ── 状态读取 ─────────────────────────────────────────────────────────────
    def _read_live(self) -> dict[str, Any] | None:
        try:
            value = json.loads(self._live_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        return value if isinstance(value, dict) else None

    def status(self) -> dict[str, Any]:
        with self._lock:
            state = deepcopy(self._state)
        if state["status"] in {"queued", "running"}:
            live = self._read_live()
            if live:
                for key in ("batch_id", "stage", "runs", "batch_dir", "error"):
                    if key in live:
                        state[key] = live[key]
        state["authorization"] = self.authorization()
        return state

    # ── 启动 ────────────────────────────────────────────────────────────────
    def start(self, count: int, *, dry_run: bool = False) -> dict[str, Any]:
        """dry_run 仅供本机 QA 硬件使用（rule-baseline 免费链路），观察者端点从不传入。"""
        count = int(count)
        if not 1 <= count <= 10:
            raise ValueError("real batch count must be between 1 and 10")
        with self._lock:
            if self._state["status"] in {"queued", "running"}:
                raise RealRunAlreadyRunning("a real run is already active")
            source = self._source()
            reasons: list[str] = []
            if source is None:
                reasons.append("未就绪：B-SCALE 冻结源数据路径未配置或不可读（AGENTSHIELD_BSCALE_DB 或 var/real_run/config.json）。")
            approved = self._approval()
            cap: float | None = None
            if not dry_run:
                values = self.env_loader()
                if not values.get("DEEPSEEK_API_KEY"):
                    reasons.append("未配置：本机 .env 缺少 DEEPSEEK_API_KEY（由负责人在本机后端填写；不进入前端或仓库）。")
                if approved is None:
                    reasons.append("未授权：当前阶段没有生效的付费预算批准记录；付费模型调用默认关闭、逐次批准。")
                else:
                    requested = STAGE_CAPS.get(count, round(PER_RUN_CAP_CNY * count, 2))
                    if requested > approved + 1e-9:
                        reasons.append(f"未批准该规模：请求上限 ¥{requested:.2f} 超出已批 ¥{approved:.2f}；请先补充预算批准。")
                    else:
                        cap = requested
            if reasons:
                raise RealRunNotAuthorized(reasons)
            seed = "agentshield-bscale-web-" + secrets.token_hex(16)
            prefix = "bscale-web-dryrun" if dry_run else DEFAULT_PREFIX
            command = [sys.executable, str(self.orchestrator), "--count", str(count), "--seed", seed,
                       "--prefix", prefix, "--status", str(self._live_path), "--work-dir", str(self._var_dir),
                       "--gold-dir", str(self.gold_root), "--source-db", str(source)]
            if dry_run:
                command += ["--config", "configs/runner/rule-baseline-v0.1.json"]
            else:
                command += ["--paid", "--cap", str(cap)]
            self._var_dir.mkdir(parents=True, exist_ok=True)
            if self._live_path.exists():
                self._live_path.unlink()
            self._state = {**self._idle(), "status": "queued", "count": count, "seed": seed,
                           "paid": not dry_run, "cap_cny": cap}
            self._persist()
            try:
                self._process = subprocess.Popen(command, cwd=self.project_root,
                                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except OSError:
                self._state.update({"status": "failed", "error_code": "ORCHESTRATOR_SPAWN_FAILED"})
                self._persist()
                raise
            threading.Thread(target=self._watch, name="real-run-monitor", daemon=True).start()
        # status() 会再次获取同一把非可重入锁：必须在锁外调用，否则端点死锁。
        return self.status()

    def _watch(self) -> None:
        while self._process is not None and self._process.poll() is None:
            time.sleep(1)
        live = self._read_live() or {}
        stage = live.get("stage")
        with self._lock:
            if stage == "completed":
                self._state.update({"status": "completed", "stage": "completed",
                                    "batch_id": live.get("batch_id") or self._state.get("batch_id"),
                                    "runs": live.get("runs", []), "batch_dir": live.get("batch_dir"),
                                    "error_code": None, "error": None})
            else:
                self._state.update({"status": "failed",
                                    "batch_id": live.get("batch_id") or self._state.get("batch_id"),
                                    "stage": stage or "failed", "runs": live.get("runs", []),
                                    "error_code": "ORCHESTRATOR_FAILED" if stage == "failed" else "RUN_DEV_FAILED",
                                    "error": live.get("error")})
            self._persist()
            state = deepcopy(self._state)
        if state["status"] == "completed" and state.get("batch_id") and self.on_complete is not None:
            try:
                self.on_complete(state["batch_id"])
            except Exception:
                pass

    # ── 持久化与恢复 ────────────────────────────────────────────────────────
    def _persist(self) -> None:
        try:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            temp = self.state_path.with_suffix(".json.tmp")
            temp.write_text(json.dumps(self._state, ensure_ascii=False), encoding="utf-8")
            os.replace(temp, self.state_path)
        except OSError:
            pass

    def _recover(self) -> dict[str, Any] | None:
        try:
            saved = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if not isinstance(saved, dict) or saved.get("status") not in {"completed", "failed", "queued", "running"}:
            return None
        if saved["status"] in {"queued", "running"}:
            live = self._read_live() or {}
            if live.get("stage") == "completed":
                saved.update({"status": "completed", "stage": "completed",
                              "batch_id": live.get("batch_id") or saved.get("batch_id"),
                              "runs": live.get("runs", []), "batch_dir": live.get("batch_dir")})
            else:
                saved.update({"status": "failed", "error_code": "REAL_BATCH_INTERRUPTED"})
        batch_id = saved.get("batch_id")
        if saved["status"] == "completed":
            if not isinstance(batch_id, str) or not (self.project_root / "artifacts/c_l0/runs" / batch_id).is_dir():
                return None
        state = self._idle()
        state.update({key: value for key, value in saved.items() if key in state})
        return state
