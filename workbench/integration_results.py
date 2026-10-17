"""Read-only adapter for the fixed A/C L0 delivery artifacts.

The adapter exposes a small, validated view. It never accepts a filesystem path
from the browser and never executes an Agent, evaluator, or insurance function.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import threading
from typing import Any, Literal

from jsonschema import Draft202012Validator
from pydantic import BaseModel, ConfigDict

from actuarial.contracts import ResearchContract
from contracts import models as b_models
from evaluator.models import LossResult


SECRET_KEYS = {
    "session_token", "admin_token", "authorization", "api_key",
    "access_token", "password", "secret",
}


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ClaimResult(Strict):
    event_id: str
    contract_version: str
    currency: Literal["CNY"]
    net_loss_cents: int | None
    loss_status: Literal["verified", "needs_review"]
    coverage_status: Literal["covered", "excluded", "needs_review"]
    claim_status: Literal["assessed", "not_covered", "needs_review"]
    payout_cents: int | None
    retained_loss_cents: int | None
    commercial_quote: Literal[False]


def _read_json(path: Path) -> Any:
    if not path.is_file() or path.stat().st_size > 5 * 1024 * 1024:
        raise ValueError(f"missing or oversized integration file: {path.name}")
    return json.loads(path.read_text(encoding="utf-8"))


def _has_secret_key(value: Any) -> bool:
    if isinstance(value, dict):
        return any(str(key).lower() in SECRET_KEYS or _has_secret_key(child) for key, child in value.items())
    if isinstance(value, list):
        return any(_has_secret_key(child) for child in value)
    return False


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_json_sha256(value: Any) -> str:
    data = (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    return hashlib.sha256(data).hexdigest()


class IntegrationResults:
    """Validated catalog of complete delivery run folders under one fixed root."""

    def __init__(self, runs_root: Path, project_root: Path):
        self.runs_root = runs_root.resolve()
        self.project_root = project_root.resolve()
        self._lock = threading.RLock()
        self._runs: dict[str, dict[str, Any]] = {}
        self.contract = self._load_contract()
        self.quote_result = self._load_quote()
        self.p0_products = self._load_p0_products()
        self._scan()

    def _load_contract(self) -> dict[str, Any]:
        raw = _read_json(self.project_root / "configs/insurance/research_contract_v0.1.json")
        ResearchContract.from_mapping(raw)
        return raw

    def _load_quote(self) -> dict[str, Any]:
        raw = _read_json(self.project_root / "contracts/quote_result_A_v0.1_engineering_example.json")
        schema = _read_json(self.project_root / "contracts/quote_result_A_v0.1_candidate.schema.json")
        Draft202012Validator(schema).validate(raw)
        if raw.get("commercial_quote") is not False or raw.get("status") != "illustrative":
            raise ValueError("A engineering QuoteResult must remain illustrative and non-commercial")
        return raw

    def _load_p0_products(self) -> dict[str, Any]:
        raw = _read_json(self.project_root / "configs/insurance/research_products_P0_v0.1.json")
        if (raw.get("schema") != "AgentShield.P0_two_research_contracts.v0.1"
                or raw.get("commercial_quote") is not False
                or raw.get("annual_aggregate_enforced_in_A0") is not False
                or raw.get("premium_status") != "insufficient_evidence"):
            raise ValueError("invalid A-P0 research product boundary")
        plans = raw.get("plans")
        if not isinstance(plans, list) or {plan.get("product_id") for plan in plans} != {
                "AgentShield-Core", "AgentShield-Plus"}:
            raise ValueError("invalid A-P0 research product set")
        for plan in plans:
            if (plan.get("commercial_quote") is not False
                    or plan.get("annual_aggregate_limit_status") != "display_only_not_enforced"):
                raise ValueError("A-P0 products must remain non-commercial and display-only")
            for key in ("deductible_cents", "coinsurance_bp", "occurrence_limit_cents",
                        "annual_aggregate_limit_cents"):
                if not isinstance(plan.get(key), int) or plan[key] < 0:
                    raise ValueError(f"invalid A-P0 product amount: {key}")
        return raw

    def _scan(self) -> None:
        with self._lock:
            scanned: dict[str, dict[str, Any]] = {}
            if self.runs_root.is_dir():
                required = ("manifest.json", "evidence.json", "loss_result.json", "claim_A0.json")
                for folder in sorted(path.parent for path in self.runs_root.glob("*/*/manifest.json")):
                    if not all((folder / name).is_file() for name in required):
                        continue
                    relative = folder.relative_to(self.runs_root).as_posix()
                    run_id = hashlib.sha256(relative.encode("utf-8")).hexdigest()[:20]
                    scanned[run_id] = self._load_run(folder, run_id, relative)
            self._runs = scanned

    def refresh(self) -> None:
        self._scan()

    def refresh_batch(self, batch_id: str) -> None:
        batch_root = (self.runs_root / batch_id).resolve()
        if batch_root.parent != self.runs_root:
            raise ValueError("invalid integration batch identity")
        required = ("manifest.json", "evidence.json", "loss_result.json", "claim_A0.json")
        scanned: dict[str, dict[str, Any]] = {}
        if batch_root.is_dir():
            for folder in sorted(path.parent for path in batch_root.glob("*/manifest.json")):
                if not all((folder / name).is_file() for name in required):
                    continue
                relative = folder.relative_to(self.runs_root).as_posix()
                run_id = hashlib.sha256(relative.encode("utf-8")).hexdigest()[:20]
                scanned[run_id] = self._load_run(folder, run_id, relative)
        with self._lock:
            self._runs = {key: value for key, value in self._runs.items()
                          if value["summary"]["batch_id"] != batch_id}
            self._runs.update(scanned)

    def _load_run(self, folder: Path, run_id: str, relative: str) -> dict[str, Any]:
        manifest = _read_json(folder / "manifest.json")
        evidence = b_models.EvidenceBundle.model_validate(_read_json(folder / "evidence.json")).model_dump(mode="json")
        loss = LossResult.model_validate(_read_json(folder / "loss_result.json")).model_dump(mode="json")
        claim = ClaimResult.model_validate(_read_json(folder / "claim_A0.json")).model_dump(mode="json")
        for value in (manifest, evidence, loss, claim):
            if _has_secret_key(value):
                raise ValueError(f"credential-shaped field in integration run: {relative}")

        session = evidence["final_snapshot"]["session"]
        identity = loss["identity"]
        for key in ("case_id", "session_id", "episode_id", "config_id", "execution_source"):
            actual = session["sources"]["execution_source"] if key == "execution_source" else session[key]
            if manifest.get(key) != actual or identity.get(key) != actual:
                raise ValueError(f"identity mismatch for {key}: {relative}")
        raw_evidence_sha256 = _sha256(folder / "evidence.json")
        canonical_evidence_sha256 = _canonical_json_sha256(evidence)
        if manifest.get("evidence_sha256") != canonical_evidence_sha256:
            raise ValueError(f"canonical evidence digest mismatch: {relative}")
        if manifest.get("counts_as_formal_run") is not False:
            raise ValueError(f"delivery run must remain non-formal: {relative}")
        expected_event = identity["episode_id"] or identity["case_id"]
        if claim["event_id"] != expected_event:
            raise ValueError(f"claim identity mismatch: {relative}")
        if claim["loss_status"] != loss["loss_status"] or claim["net_loss_cents"] != loss["net_loss_cents"]:
            raise ValueError(f"claim/loss mismatch: {relative}")
        if claim["coverage_status"] != loss["coverage_status_input"]:
            raise ValueError(f"claim coverage mismatch: {relative}")
        if loss["loss_status"] == "needs_review" and (loss["net_loss_cents"] is not None or claim["payout_cents"] is not None):
            raise ValueError(f"unreviewed run exposes a loss or payout: {relative}")

        p0_claims = None
        p0_path = folder / "claim_core_plus.json"
        if p0_path.is_file():
            p0_claims = _read_json(p0_path)
            if _has_secret_key(p0_claims):
                raise ValueError(f"credential-shaped field in A-P0 result: {relative}")
            if (p0_claims.get("display_schema") != "AgentShield.A_P0_claim_comparison.v0.1"
                    or p0_claims.get("commercial_quote") is not False
                    or p0_claims.get("real_agent_insurance_claim") is not False
                    or p0_claims.get("source_type") != "observed_agent_execution_pending_review"
                    or p0_claims.get("event_id") != expected_event
                    or p0_claims.get("loss_status") != loss["loss_status"]
                    or p0_claims.get("net_loss_cents") != loss["net_loss_cents"]
                    or p0_claims.get("coverage_status") != loss["coverage_status_input"]):
                raise ValueError(f"A-P0 result identity or status mismatch: {relative}")
            rows = p0_claims.get("claims")
            if not isinstance(rows, list) or {row.get("product_id") for row in rows} != {
                    "AgentShield-Core", "AgentShield-Plus"}:
                raise ValueError(f"A-P0 result product set mismatch: {relative}")
            versions = {plan["product_id"]: plan["contract_version"] for plan in self.p0_products["plans"]}
            for row in rows:
                if (row.get("contract_version") != versions[row["product_id"]]
                        or row.get("event_id") != expected_event
                        or row.get("commercial_quote") is not False
                        or row.get("loss_status") != loss["loss_status"]
                        or row.get("net_loss_cents") != loss["net_loss_cents"]
                        or row.get("coverage_status") != loss["coverage_status_input"]):
                    raise ValueError(f"A-P0 claim mismatch: {relative}")
                if loss["loss_status"] == "needs_review" and (
                        row.get("claim_status") != "needs_review"
                        or row.get("payout_cents") is not None
                        or row.get("retained_loss_cents") is not None):
                    raise ValueError(f"unreviewed A-P0 claim exposes money: {relative}")

        summary = {
            "run_id": run_id,
            "batch_id": relative.split("/", 1)[0],
            "label": manifest.get("label", folder.name),
            "case_id": session["case_id"],
            "session_id": session["session_id"],
            "episode_id": session["episode_id"],
            "config_id": session["config_id"],
            "execution_source": session["sources"]["execution_source"],
            "provider": manifest.get("adapter", {}).get("provider"),
            "model": manifest.get("adapter", {}).get("model"),
            "run_status": manifest.get("run_status"),
            "task_outcome": manifest.get("task_outcome"),
            "loss_status": loss["loss_status"],
            "claim_status": claim["claim_status"],
            "counts_as_formal_run": False,
            "total_committed_cents": loss["total_committed_cents"],
            "evidence_digest_status": (
                "raw_file_match" if raw_evidence_sha256 == canonical_evidence_sha256
                else "canonical_json_match_raw_delivery_differs"
            ),
        }
        return {
            "summary": summary,
            "evidence": evidence,
            "loss_result": loss,
            "claim": claim,
            "contract": self.contract,
            "quote_result": self.quote_result,
            "p0_products": self.p0_products,
            "p0_claim_comparison": p0_claims,
        }

    def catalog(self) -> dict[str, Any]:
        with self._lock:
            rows = [value["summary"] for value in self._runs.values()]
            rows.sort(key=lambda row: (row["execution_source"] != "observed_agent_execution", row["batch_id"], row["label"]))
            return {"contract_version": "abcd-integration-0.1-candidate", "runs": rows}

    def detail(self, run_id: str) -> dict[str, Any]:
        with self._lock:
            try:
                return self._runs[run_id]
            except KeyError:
                raise KeyError("integration run not found") from None
