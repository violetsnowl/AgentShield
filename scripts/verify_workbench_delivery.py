"""Stage 03 packaging/protection checks; no old database access or modification."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import zipfile

from contracts import models as m
from scripts.export_contracts import products
from scripts.export_frontend_contract import products as frontend_products

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    output = (ROOT / args.output_dir).resolve()
    if not output.is_relative_to(ROOT / "artifacts/pro_bd_sprint/03"):
        raise SystemExit("Stage 03 outputs only")
    output.mkdir(parents=True, exist_ok=False)
    for path in ("frontend/README.md", "frontend/package-lock.json", "frontend/dist/index.html",
                 "docs/decisions/BD_observer_v0.1.md", "contracts/workbench_examples.json",
                 "artifacts/pro_bd_sprint/03/RESULTS.md", "NEXT_STEPS.md"):
        assert (ROOT / path).is_file(), path
    for name, data in products(True).items():
        assert json.loads((ROOT / "contracts" / name).read_text(encoding="utf-8")) == data, name
    for name, data in frontend_products().items():
        assert (ROOT / "frontend/src/generated" / name).read_text(encoding="utf-8") == data, name
    samples = json.loads((ROOT / "contracts/workbench_examples.json").read_text(encoding="utf-8"))
    m.FixtureCatalog.model_validate(samples["fixtures"])
    m.SessionPage.model_validate(samples["sessions_page"])
    for page in samples["event_pages"]:
        m.EventPage.model_validate(page)
    assert "session_token" not in samples["observer_created_session"]
    m.SessionStatus.model_validate(samples["observer_created_session"]["session"])
    m.CaseContext.model_validate(samples["observer_created_session"]["case_context"])
    before = json.loads((ROOT / "artifacts/pro_bd_sprint/03/checkpoints/before_03_manifest.json").read_text(encoding="utf-8"))
    protected = [row for row in before["files"] if row["path"].startswith(("artifacts/", "docs/spec/", "docs/audit/", "tasks/", "migrations/", "sandbox/fixtures/"))]
    for row in protected:
        assert hashlib.sha256((ROOT / row["path"]).read_bytes()).hexdigest() == row["sha256"], row["path"]
    with zipfile.ZipFile(ROOT / "artifacts/pro_bd_sprint/03/checkpoints/before_03.zip") as archive:
        def nodes(source, cls):
            tree = ast.parse(source)
            return next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == cls).body
        old_store = nodes(archive.read("sandbox/store.py").decode("utf-8-sig"), "Store")
        new_store = {node.name: node for node in nodes((ROOT / "sandbox/store.py").read_text(encoding="utf-8-sig"), "Store") if isinstance(node, ast.FunctionDef)}
        unchanged = []
        for node in old_store:
            if isinstance(node, ast.FunctionDef) and node.name != "events":
                assert ast.dump(node) == ast.dump(new_store[node.name]), node.name
                unchanged.append(node.name)
        old_models = ast.parse(archive.read("contracts/models.py").decode("utf-8-sig"))
        new_models = ast.parse((ROOT / "contracts/models.py").read_text(encoding="utf-8-sig"))
        classes = {node.name: node for node in new_models.body if isinstance(node, ast.ClassDef)}
        for node in old_models.body:
            if isinstance(node, ast.ClassDef):
                assert ast.dump(node) == ast.dump(classes[node.name]), node.name
    paths = [ROOT / name for name in ("README_B.md", "NEXT_STEPS.md", ".env.example", ".gitignore", "requirements.lock")]
    for directory in ("api", "sandbox", "workbench", "scripts", "tests", "contracts", "migrations", "docs", "tasks", "frontend"):
        for path in (ROOT / directory).rglob("*"):
            if path.is_file() and not set(path.relative_to(ROOT).parts) & {"node_modules", "__pycache__", "dist"}:
                paths.append(path)
    manifest = {"b_version": m.VERSION, "observer_version": "observer-0.1-candidate", "files": [
        {"path": path.relative_to(ROOT).as_posix(), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        for path in sorted(set(paths))]}
    (output / "source_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    record = {"protected_files_verified": len(protected), "unchanged_store_methods": unchanged,
              "all_preexisting_wire_classes_unchanged": True, "migrations_added": 0,
              "old_database_hashes": "NOT_VERIFIED_PERMISSION_DENIED; not accessed or modified",
              "consumer_acceptance": "pending_A_C_D", "source_files": len(manifest["files"])}
    (output / "verification.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(record))


if __name__ == "__main__":
    main()
