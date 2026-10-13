"""Verify sealed stage05 archives and unpack slim payload exclusively to a new directory."""
import hashlib
import json
from pathlib import Path
import zipfile

root = Path.cwd()
stage = root / "artifacts/pro_bd_sprint/05"
sha = lambda raw: hashlib.sha256(raw).hexdigest()
archives = []
slim_name = "AgentShield_BD_Handoff_Stage05_2026-10-12"
for folder, name in (("packages", slim_name), ("checkpoints", "after_05"), ("checkpoints", "before_05")):
    p = stage / folder / (name + ".zip")
    manifest = json.loads((stage / folder / (name + "_manifest.json")).read_text("utf-8"))
    assert sha(p.read_bytes()) == manifest["archive_sha256"], name
    with zipfile.ZipFile(p) as z:
        assert z.testzip() is None
        assert not any(n.lower().endswith(".zip") for n in z.namelist())
        assert all(sha(z.read(r["path"])) == r["sha256"] for r in manifest["files"])
        if name != "before_05":
            assert all(sha((root / r["path"]).read_bytes()) == r["sha256"] for r in manifest["files"])
    archives.append({"path": p.relative_to(root).as_posix(), "sha256": manifest["archive_sha256"],
                     "bytes": p.stat().st_size, "payload_files": len(manifest["files"]), "nested_zips": 0})
fresh = root / "var/stage05-final-package-verification"
assert not fresh.exists()
fresh.mkdir()
with zipfile.ZipFile(stage / "packages" / (slim_name + ".zip")) as z:
    for item in z.infolist():
        p = (fresh / item.filename).resolve()
        assert p.is_relative_to(fresh) and not p.exists(), item.filename
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(z.read(item))
manifest = json.loads((fresh / "PACKAGE_MANIFEST.json").read_text("utf-8"))
assert all(sha((fresh / r["path"]).read_bytes()) == r["sha256"] for r in manifest["files"])
runtime = json.loads((stage / "fresh_runtime_manifest.json").read_text("utf-8"))["runtime_and_test_files"]
for r in runtime:
    assert sha((fresh / r["path"]).read_bytes()) == r["sha256"], r["path"]
for rel in ("requirements.lock", "frontend/package-lock.json", "frontend/package.json", "frontend/tsconfig.json", "frontend/vite.config.mjs", "frontend/index.html"):
    assert (fresh / rel).read_bytes() == (root / "var/stage05-reception" / rel).read_bytes()
for name in ("README_RECEIVE.md", "docs/handoff/BD_CURRENT_STATE.md", "docs/handoff/BD_to_A_CHECKLIST.md",
             "docs/handoff/BD_to_C_CHECKLIST.md", "NEXT_STEPS.md", "frontend/src/generated/evidence.validator.d.cts"):
    assert (fresh / name).is_file(), name
result = {"archives_verified": archives, "final_slim_unpack": str(fresh.relative_to(root)),
          "all_slim_payload_hashes_match": True, "tested_runtime_and_tests_identical": len(runtime),
          "locks_build_inputs_identical_to_tested_reception": True,
          "full_history_retained_in_original_workspace": True, "new_source_features": False,
          "second_machine": False, "second_operator": False, "A_C_acceptance": "pending",
          "pending_install": "Fresh Python pip TLS EOF; runtime checks reused original locked .venv",
          "receipt_placement": "Created after sealed archives; this receipt is external, not recursively included in them"}
with (stage / "final_delivery_receipt.json").open("x", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
print(json.dumps(result, ensure_ascii=True, indent=2))
