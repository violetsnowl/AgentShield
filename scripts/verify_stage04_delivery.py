"""Stage 04 preservation, contract/sample and deliverable checks. No business DB writes."""
import argparse
import hashlib
import json
from pathlib import Path

from contracts.models import EvidenceBundle
from scripts.export_contracts import products
from scripts.export_frontend_contract import products as frontend_products

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    output = (ROOT / args.output_dir).resolve()
    if not output.is_relative_to(ROOT / "artifacts/pro_bd_sprint/04"):
        raise SystemExit("Stage 04 output only")
    output.mkdir(parents=True, exist_ok=False)
    baseline = json.loads((ROOT / "artifacts/pro_bd_sprint/04/checkpoints/before_04_manifest.json").read_text("utf-8"))
    protected_prefixes = ("api/", "sandbox/", "contracts/", "migrations/", "workbench/", "docs/spec/", "docs/audit/", "tasks/", "artifacts/b_bootstrap/", "artifacts/pro_bd_sprint/01/", "artifacts/pro_bd_sprint/02/", "artifacts/pro_bd_sprint/03/")
    protected = [r for r in baseline["files"] if r["path"].startswith(protected_prefixes)]
    for row in protected:
        assert hashlib.sha256((ROOT / row["path"]).read_bytes()).hexdigest() == row["sha256"], row["path"]
    for name, content in products(True).items():
        assert json.loads((ROOT / "contracts" / name).read_text("utf-8")) == content, name
    for name, content in frontend_products().items():
        assert (ROOT / "frontend/src/generated" / name).read_text("utf-8") == content, name
    for name in ("README_B.md", "NEXT_STEPS.md", "frontend/README.md", "docs/handoff/BD_to_A_C.md",
                 "docs/handoff/B_to_C.md", "docs/decisions/BD_display_v0.2.md", "frontend/dist/index.html",
                 "artifacts/pro_bd_sprint/04/RESULTS.md"):
        assert (ROOT / name).is_file(), name
    sample = json.loads((ROOT / "contracts/bd_handoff_example_v0.1.json").read_text("utf-8"))
    raw = (ROOT / sample["evidence_file"]).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == sample["evidence_sha256"]
    evidence = EvidenceBundle.model_validate_json(raw).model_dump()
    assert all(evidence["final_snapshot"]["session"][key] == value for key, value in sample["identity"].items())
    refund = next(r for r in evidence["refunds"] if r["transaction_id"] == sample["trace"]["transaction_id"])
    assert refund["order_id"] == sample["trace"]["order_id"]
    assert sample["trace"]["ledger_entry_id"] == next(r for r in evidence["ledger"] if r["transaction_id"] == refund["transaction_id"])["entry_id"]
    assert sample["trace"]["event_seqs"] == [r["seq"] for r in evidence["events"] if r["transaction_id"] == refund["transaction_id"]]
    assert sample["LossResult"] is None and sample["QuoteResult"] is None and sample["commercial_quote"] is False
    databases = json.loads((ROOT / "artifacts/pro_bd_sprint/04/database_preservation_before.json").read_text("utf-8"))
    for row in databases["backups"]:
        assert hashlib.sha256((ROOT / row["path"]).read_bytes()).hexdigest() == row["original_sha256"], row["path"]
    changed = [r["path"] for r in baseline["files"] if hashlib.sha256((ROOT / r["path"]).read_bytes()).hexdigest() != r["sha256"]]
    # Sensitive material is not collected here. Runtime secrets are scanned by the
    # browser harness in requests/responses/bundles and by its server-side driver.
    frontend_sources = list((ROOT / "frontend/src").rglob("*"))
    for p in frontend_sources:
        if p.is_file():
            text = p.read_text("utf-8")
            assert "VITE_ADMIN" not in text and "localStorage.setItem" not in text and "sessionStorage.setItem" not in text, p
    result = {"protected_files_unchanged": len(protected), "B_api_store_models_observer_migrations_unchanged": True,
              "contract_exports_match": True, "handoff_sample_matches_real_HTTP": True,
              "readable_original_databases_hash_unchanged": len(databases["backups"]),
              "unverified_database_paths": databases["unverified"], "changed_preexisting_files": changed,
              "new_formal_A_C_contracts": False, "A_C_acceptance": "pending", "stage": "04"}
    (output / "verification.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", "utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "unverified_database_paths"}, ensure_ascii=True))


if __name__ == "__main__":
    main()
