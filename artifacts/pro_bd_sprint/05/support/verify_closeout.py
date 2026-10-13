"""Read-only preservation and slim-payload check. Requires the original history workspace."""
import hashlib
import json
from pathlib import Path
import re
from scripts.stage05_handoff import files

root = Path.cwd()
stage = root / "artifacts/pro_bd_sprint/05"
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
baseline = json.loads((root / "artifacts/pro_bd_sprint/04/checkpoints/after_04_manifest.json").read_text("utf-8"))
allowed = {"docs/handoff/BD_to_A_C.md", "frontend/README.md", "NEXT_STEPS.md", "scripts/run_workbench_checks.py"}
changed = [r["path"] for r in baseline["files"] if sha(root / r["path"]) != r["sha256"]]
assert set(changed) == allowed, changed
before = json.loads((stage / "checkpoints/before_05_manifest.json").read_text("utf-8"))
assert sha(stage / "checkpoints/before_05.zip") == before["archive_sha256"]
# Each complete previous document is still present below the current handoff notice.
import zipfile
with zipfile.ZipFile(stage / "checkpoints/before_05.zip") as z:
    for name in allowed - {"scripts/run_workbench_checks.py"}:
        # Text-mode reads normalize Windows line endings; compare document text
        # with the same normalization, while archive byte hashes stay separate.
        assert z.read(name).decode("utf-8").replace("\r\n", "\n") in (root / name).read_text("utf-8"), name
db = json.loads((stage / "database_preservation_before.json").read_text("utf-8"))
assert all(sha(root / r["path"]) == r["sha256"] for r in db["readable"])
runtime = json.loads((stage / "fresh_runtime_manifest.json").read_text("utf-8"))["runtime_and_test_files"]
for r in runtime:
    assert sha(root / r["path"]) == r["sha256"], r["path"]
    assert sha(root / "var/stage05-reception" / r["path"]) == r["sha256"], r["path"]
for rel in ("requirements.lock", "frontend/package-lock.json", "frontend/package.json", "frontend/tsconfig.json", "frontend/vite.config.mjs", "frontend/index.html"):
    assert sha(root / rel) == sha(root / "var/stage05-reception" / rel), rel
build = list((root / "frontend/dist").rglob("*"))
for p in build:
    if p.is_file():
        assert sha(p) == sha(root / "var/stage05-reception" / p.relative_to(root))
hits = []
def inspect(value, rel):
    if isinstance(value, dict):
        for k, v in value.items():
            if k.lower() in {"session_token", "admin_token", "api_key", "access_token", "refresh_token", "authorization"} and isinstance(v, str) and len(v) > 8:
                hits.append({"path": rel, "field": k})
            inspect(v, rel)
    elif isinstance(value, list):
        for v in value:
            inspect(v, rel)
payload = list(files(True))
for p, rel in payload:
    assert not p.suffix.lower() in {".zip", ".db", ".sqlite", ".sqlite3", ".key", ".pem", ".p12"}
    text = p.read_text("utf-8", errors="replace")
    if p.suffix == ".json":
        try:
            inspect(json.loads(text), rel)
        except ValueError:
            pass
    for kind, pattern in (("provider_key", r"\bsk-(?:proj-)?[A-Za-z0-9_-]{24,}"),
                          ("private_key", r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
                          ("literal_bearer", r"Bearer [A-Za-z0-9_-]{24,}")):
        if re.search(pattern, text):
            hits.append({"path": rel, "pattern": kind})
assert not hits, hits
for label in ("backend_native", "http_native", "frontend_tests_native", "frontend_build", "frontend_types", "contracts", "frontend_contract",
              "browser_original", "browser_integration", "observer_security", "environment", "fresh_frontend_tests", "fresh_frontend_build_r2",
              "fresh_backend_existing_python", "fresh_http_existing_python", "fresh_cli_startup_r3", "fresh_contracts", "fresh_frontend_contract",
              "fresh_environment_existing_python"):
    assert json.loads((stage / "checks" / (label + ".json")).read_text("utf-8"))["exit_code"] == 0, label
result = {"stage": "05", "after04_baseline_files": len(baseline["files"]), "unchanged": len(baseline["files"]) - len(changed),
          "changed_preexisting_files": changed, "B_frontend_runtime_contracts_migrations_unchanged": True,
          "prior_document_text_preserved": True, "readable_databases_hash_unchanged": len(db["readable"]),
          "unverified_database_paths": db["unverified"], "tested_reception_runtime_and_test_files_identical": len(runtime),
          "fresh_build_bit_identical": True, "scanned_slim_files_before_final_results": len(payload), "credential_scan_findings": hits,
          "credential_scan_scope": "Text patterns + populated JSON credential fields; complements runtime-secret checks in browser suites, not proof about all unknown secret formats",
          "all_required_native_checks_exit_zero": True, "new_python_install": "failed_TLS_EOF_existing_locked_environment_reused",
          "second_machine": False, "different_operator": False, "A_C_acceptance": "pending", "model_calls": 0, "real_payment_calls": 0}
with (stage / "closeout_verification.json").open("x", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
print(json.dumps({k: v for k, v in result.items() if k != "unverified_database_paths"}, ensure_ascii=True))
