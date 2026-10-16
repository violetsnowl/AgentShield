"""Recompute LossResult and ClaimResult from saved evidence plus an A/D obligation spec.

The runner and prompts do not call this. Pass the spec path only after the episode
has finished. No network and no private Gold search.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

from actuarial.claims import calculate_claim
from evaluator.obligations import load_spec
from evaluator.verify import claim_event, evaluate_evidence

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "configs/insurance/research_contract_v0.1.json"


def reverify(evidence: dict, spec: dict | None, contract: dict, evidence_sha256: str | None = None) -> tuple[dict, dict]:
    loss = evaluate_evidence(evidence, spec, evidence_sha256)
    claim = calculate_claim(claim_event(loss), contract)
    return loss, claim


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", required=True)
    parser.add_argument("--obligations", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    evidence_path = Path(args.evidence)
    raw = evidence_path.read_bytes()
    evidence = json.loads(raw.decode("utf-8"))
    spec = load_spec(Path(args.obligations))
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    loss, claim = reverify(evidence, spec, contract, hashlib.sha256(raw).hexdigest())
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "loss_result.json").write_text(json.dumps(loss, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "claim_A0.json").write_text(json.dumps(claim, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"loss_status": loss["loss_status"], "net_loss_cents": loss["net_loss_cents"],
                      "claim_status": claim["claim_status"], "payout_cents": claim["payout_cents"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
