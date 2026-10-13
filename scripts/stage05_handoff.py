"""Stage 05 packaging only. No DB access, installs, migrations or source mutations."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / "artifacts/pro_bd_sprint/05"
SKIP = {".venv", "node_modules", "__pycache__", "dist", "var", ".git", ".agents", ".codex", "private", "gold", "holdout", "secrets"}
SUFFIXES = {".py", ".md", ".json", ".jsonl", ".ts", ".tsx", ".cts", ".mts", ".mjs", ".cjs", ".css", ".html", ".svg", ".sql", ".lock", ".txt", ".log", ".png"}
HISTORICAL = {
    "artifacts/b_bootstrap/http_smoke/evidence_sample.json",
    "artifacts/b_bootstrap/http_smoke/events_sample.jsonl",
    "artifacts/b_bootstrap/http_smoke/http_responses.json",
    "artifacts/pro_bd_sprint/01/patch_http_evidence/evidence_sample.json",
    "artifacts/pro_bd_sprint/04/integration_browser_evidence_r2/dev-refund-v2_evidence.json",
    *(f"artifacts/pro_bd_sprint/{n:02d}/RESULTS.md" for n in range(1, 5)),
}


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def files(slim):
    for directory, dirs, names in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d.lower() not in SKIP]
        for name in sorted(names):
            p = Path(directory) / name
            rel = p.relative_to(ROOT).as_posix()
            if p.is_symlink() or p.suffix.lower() not in SUFFIXES and name not in {".gitignore", ".env.example"}:
                continue
            if name.startswith(".env") and name != ".env.example":
                continue
            if rel.startswith(("artifacts/pro_bd_sprint/05/checkpoints/", "artifacts/pro_bd_sprint/05/packages/")):
                continue
            if slim:
                if rel.startswith("docs/audit/") and p.suffix != ".md" and name != "observer_extra_probes.py":
                    continue
                if rel.startswith("artifacts/"):
                    if rel not in HISTORICAL and not rel.startswith("artifacts/pro_bd_sprint/05/"):
                        continue
                    # Current command logs + small HTTP evidence retained; screenshots and
                    # browser full exports stay in the original workspace, not the slim ZIP.
                    if any(part in rel for part in ("/browser_original/", "/browser_integration/", "/fresh_browser/")):
                        continue
                    if p.suffix == ".png":
                        continue
            yield p, rel


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("candidate", "slim", "checkpoint"))
    parser.add_argument("--name", required=True)
    args = parser.parse_args()
    if not args.name.replace("_", "").replace("-", "").isalnum():
        raise SystemExit("Simple new archive name required")
    folder = STAGE / ("checkpoints" if args.mode == "checkpoint" else "packages")
    folder.mkdir(parents=True, exist_ok=True)
    archive = folder / (args.name + ".zip")
    manifest = folder / (args.name + "_manifest.json")
    if archive.exists() or manifest.exists():
        raise SystemExit("Use a new name: archives/manifests are never overwritten")
    rows = []
    with zipfile.ZipFile(archive, "x", zipfile.ZIP_DEFLATED) as z:
        for p, rel in sorted(files(args.mode != "checkpoint")):
            raw = p.read_bytes()
            z.writestr(rel, raw)
            rows.append({"path": rel, "sha256": digest(raw), "bytes": len(raw)})
        info = {"stage": "05", "mode": args.mode, "created_at": datetime.now(timezone.utc).isoformat(),
                "files": rows, "omissions": "Environments, databases, credentials, Gold/holdout, ALL ZIPs. Slim also omits full historical QA outputs/screenshots.",
                "history": "Original workspace and previous checkpoints unchanged; this is not a full historical audit replica."}
        z.writestr("PACKAGE_MANIFEST.json", json.dumps(info, ensure_ascii=False, indent=2) + "\n")
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        assert all(digest(z.read(r["path"])) == r["sha256"] for r in rows)
        assert not any(n.lower().endswith(".zip") for n in z.namelist())
    info.update(archive=archive.name, archive_sha256=digest(archive.read_bytes()), archive_bytes=archive.stat().st_size,
                verified_zip_contents=True, nested_zips=0, git="not_a_git_repository")
    manifest.write_text(json.dumps(info, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in info.items() if k != "files"}, ensure_ascii=True))


if __name__ == "__main__":
    main()
