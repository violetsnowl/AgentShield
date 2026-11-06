"""Read-only view of real-model risk batches: the control comparison and exportable accidents.

The browser only ever sends an opaque case id. Paths, Gold and raw evidence stay on this
machine, and a pack is rebuilt from evidence on every export.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from experiments.claim_pack import (ROOT, RAW_ROOT, RESULTS_ROOT, ClaimPackError, FAMILY_LABELS, PROFILE_LABELS, is_accident,
                                    latest_rows, model_of, pack_for_row, render_html, run_name)
from experiments.risk_summary import ACCIDENT_FLOOR_CENTS, BLOCKING_CODES, wilson
from workbench.integration_results import _has_secret_key

OBSERVED = "observed_agent_execution"
TASK_SET_LABELS = {"v1": "基础任务", "v2": "加难任务"}
PROFILE_ORDER = ("P0", "P1", "P2")


def case_id(batch: str, row: dict[str, Any]) -> str:
    return hashlib.sha256(f"{batch}/{run_name(row)}".encode("utf-8")).hexdigest()[:20]


def _model_label(row: dict[str, Any]) -> str:
    label = model_of(row.get("config_id")).split("/")[-1]
    return label + "（关思考）" if "nothink" in str(row.get("config_id")) else label


def _task_label(manifest: dict[str, Any]) -> str:
    # Batches from before the harder set have no task_set field; they ran the first set.
    label = TASK_SET_LABELS.get(manifest.get("task_set", "v1"), "未标注")
    families = manifest.get("families") or []
    if manifest.get("task_set") == "v2" and 0 < len(families) < 7:
        return f"{label}（{'、'.join(FAMILY_LABELS.get(family, family) for family in families)}）"
    return label


class ClaimCases:
    def __init__(self, results_root: Path = RESULTS_ROOT, raw_root: Path = RAW_ROOT, source: Path | None = None):
        self.results_root = Path(results_root)
        self.raw_root = Path(raw_root)
        self.source = source

    def _source(self) -> Path | None:
        candidates: list[Any] = [self.source, os.environ.get("AGENTSHIELD_BSCALE_DB")]
        config = ROOT / "var/real_run/config.json"
        if config.is_file():
            candidates.append(json.loads(config.read_text(encoding="utf-8")).get("source_db"))
        for candidate in candidates:
            if candidate and Path(candidate).is_file():
                return Path(candidate).resolve()
        return None

    def _batches(self) -> list[tuple[str, dict[str, Any], list[dict[str, Any]]]]:
        found = []
        if not self.results_root.is_dir():
            return found
        for folder in sorted(path for path in self.results_root.iterdir() if path.is_dir()):
            if not (folder / "results.jsonl").is_file() or not (folder / "manifest.json").is_file():
                continue
            rows = [row for row in latest_rows(folder.name, self.results_root)
                    if row.get("run_status") == "completed" and row.get("execution_source") == OBSERVED]
            if rows:
                found.append((folder.name, json.loads((folder / "manifest.json").read_text(encoding="utf-8")), rows))
        return found

    def _arm(self, batch: str, manifest: dict[str, Any], rows: list[dict[str, Any]], profile: str) -> dict[str, Any]:
        verified = [row for row in rows if row.get("loss_status") == "verified"]
        accidents = [row for row in verified if (row.get("net_loss_cents") or 0) >= ACCIDENT_FLOOR_CENTS]
        low, high = wilson(len(accidents), len(verified)) or (None, None)
        return {"batch_id": batch, "model": _model_label(rows[0]), "tasks": _task_label(manifest),
                "control_profile": profile, "control_label": PROFILE_LABELS[profile], "runs": len(verified), "accidents": len(accidents),
                "rate_low": low, "rate_high": high, "net_loss_cents": sum(row.get("net_loss_cents") or 0 for row in verified),
                "blocked_runs": sum(1 for row in verified if BLOCKING_CODES & set(row.get("rejected_codes") or []))}

    def catalog(self) -> dict[str, Any]:
        groups, cases = [], []
        for batch, manifest, rows in self._batches():
            groups.append([self._arm(batch, manifest, cell, profile) for profile in PROFILE_ORDER
                           if (cell := [row for row in rows if row["control_profile"] == profile])])
            for row in rows:
                if is_accident(row):
                    cases.append({"case_id": case_id(batch, row), "batch_id": batch, "model": _model_label(row),
                                  "control_label": PROFILE_LABELS.get(row["control_profile"], row["control_profile"]),
                                  "family_label": FAMILY_LABELS.get(row.get("family"), "未标注"),
                                  "net_loss_cents": row["net_loss_cents"], "payout_cents": row.get("payout_cents"),
                                  "claim_status": row.get("claim_status"),
                                  "available": (self.raw_root / batch / run_name(row) / "evidence.json.gz").is_file()})
        cases.sort(key=lambda row: (-row["net_loss_cents"], row["case_id"]))
        # Batches that lost money come first; a batch keeps its P0, P1, P2 order.
        groups.sort(key=lambda group: -sum(arm["accidents"] for arm in group))
        arms = [arm for group in groups for arm in group]
        return {"contract_version": "claim-cases-0.1-candidate", "commercial_quote": False, "counts_as_formal_run": False,
                "experiment_nature": "有意加难的合成任务上的压力测试，不是自然事故率", "accident_floor_cents": ACCIDENT_FLOOR_CENTS,
                "arms": arms, "cases": cases}

    def export(self, wanted: str) -> dict[str, Any]:
        """KeyError for an unknown case; ClaimPackError when evidence is absent or does not add up."""
        for batch, _, rows in self._batches():
            for row in rows:
                if is_accident(row) and case_id(batch, row) == wanted:
                    source = self._source()
                    if source is None:
                        raise ClaimPackError("task source is not configured")
                    pack, _ = pack_for_row(batch, row, source, raw_root=self.raw_root)
                    if _has_secret_key(pack):
                        raise ClaimPackError("credential-shaped field in evidence")
                    return {"filename": f"理赔材料-{pack['identity']['case_id']}-{row['control_profile']}.html",
                            "html": render_html(pack), "net_loss_cents": pack["summary"]["net_loss_cents"],
                            "payout_cents": pack["summary"]["payout_cents"]}
        raise KeyError("claim case not found")
