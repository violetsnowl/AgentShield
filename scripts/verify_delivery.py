"""Final packaging checks; does not replace transaction tests or consumer acceptance."""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import secrets

from contracts.models import VERSION

ROOT = Path(__file__).resolve().parents[1]


def run(*args):
    result = subprocess.run([sys.executable, *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    if result.returncode:
        raise RuntimeError(f"Delivery command failed: {args}; exit {result.returncode}")
    print(result.stdout.strip())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="artifacts/pro_bd_sprint/02/delivery-" + secrets.token_hex(6))
    args = parser.parse_args()
    output = ROOT / args.output_dir
    output.mkdir(parents=True, exist_ok=False)
    required = ["README_B.md", "NEXT_STEPS.md", "requirements.lock", ".env.example",
                "docs/decisions/BC_contract_v0.3.md", "docs/handoff/B_to_C.md",
                "contracts/openapi.json", "contracts/schemas.json", "contracts/tools.json",
                "contracts/examples.json", "contracts/response_examples.json",
                "contracts/evidence_example.json", "migrations/002_human_reviews.sql", "migrations/003_session_cases.sql",
                "contracts/case_examples.json", "contracts/fixture_registry.json", "contracts/development_fixture.schema.json",
                "contracts/fixture_v2_evidence_example.json", "docs/migrations/B_003_session_cases.md",
                "sandbox/fixtures/dev-refund-v2.json", "artifacts/pro_bd_sprint/02/RESULTS.md",
                "artifacts/pro_bd_sprint/01/RESULTS.md", "artifacts/b_bootstrap/http_smoke/evidence_sample.json"]
    for name in required:
        if not (ROOT / name).is_file():
            raise RuntimeError(f"Missing required deliverable: {name}")
    for line in (ROOT / "requirements.lock").read_text(encoding="utf-8-sig").splitlines():
        if line.strip():
            package, version = line.strip().split("==")
            assert importlib.metadata.version(package) == version, package
    run("-m", "pip", "check")
    run("-m", "scripts.export_contracts", "--with-openapi", "--check")
    (ROOT / "var").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="init-check-", dir=ROOT / "var") as temp:
        db = str(Path(temp) / "init.sqlite3")
        run("-m", "scripts.init_dev", "--db", db)
        run("-m", "scripts.init_dev", "--db", db)
    spec = json.loads((ROOT / "docs/spec/AgentShield_v1.1_Package/delivery_levels_v1.1.json").read_text(encoding="utf-8"))
    assert spec["implementation_status"] == "not_verified"
    assert spec["paid_runs"] == {"enable_paid_runs": False, "max_cost": 0}
    files = [ROOT / name for name in ("README_B.md", "NEXT_STEPS.md", "requirements.lock", ".env.example", ".gitignore")]
    for directory in ("api", "sandbox", "migrations", "contracts", "scripts", "tests", "docs", "tasks"):
        files += [path for path in (ROOT / directory).rglob("*") if path.is_file() and "__pycache__" not in path.parts]
    manifest = {"version": VERSION, "git_status": "not_a_git_repository", "files": [
        {"path": path.relative_to(ROOT).as_posix(), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        for path in sorted(set(files))]}
    before = json.loads((ROOT / "artifacts/pro_bd_sprint/02/checkpoints/before_02_manifest.json").read_text(encoding="utf-8"))
    historical = [entry for entry in before["files"] if entry["path"].startswith(("artifacts/", "docs/audit/", "docs/spec/", "tasks/"))
                  or entry["path"] in ("migrations/001_initial.sql", "migrations/002_human_reviews.sql", "docs/decisions/BC_contract_v0.2.md")]
    assert all(hashlib.sha256((ROOT / entry["path"]).read_bytes()).hexdigest() == entry["sha256"] for entry in historical)
    inspection = json.loads((ROOT / "artifacts/pro_bd_sprint/02/inspection.json").read_text(encoding="utf-8"))
    for entry in inspection["initial_database_files"]:
        assert hashlib.sha256((ROOT / entry["path"]).read_bytes()).hexdigest() == entry["sha256"], entry["path"]
    (output / "source_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Historical evidence, prior checkpoints, specifications and migrations preserved: {len(historical)} files match pre-stage hashes.")
    print(f"Existing database files unchanged: {len(inspection['initial_database_files'])}.")
    print(f"Required delivery files present; locked environment matches; {len(manifest['files'])} source hashes recorded.")
    print("Consumer acceptance remains pending; no team gate is marked passed.")


if __name__ == "__main__":
    main()
