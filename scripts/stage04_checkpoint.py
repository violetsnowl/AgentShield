"""Exclusive local source/evidence snapshot; databases and credentials stay private."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("name", choices=("entry_04_0", "after_04"))
    args = parser.parse_args()
    folder = ROOT / "artifacts/pro_bd_sprint/04/checkpoints"
    folder.mkdir(parents=True, exist_ok=True)
    archive = folder / (args.name + ".zip")
    exclude = {".venv", "node_modules", "__pycache__", "dist", "var", ".git", ".agents", ".codex", "private"}
    files = []
    for directory, dirs, names in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in exclude]
        for name in names:
            p = Path(directory) / name
            if p.is_relative_to(folder):
                continue
            if (name.startswith(".env") and name != ".env.example") or p.suffix in {".pem", ".key", ".p12", ".sqlite", ".sqlite3", ".pyc"}:
                continue
            files.append(p)
    records = []
    with zipfile.ZipFile(archive, "x", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(files):
            content = p.read_bytes()
            name = p.relative_to(ROOT).as_posix()
            z.writestr(name, content)
            records.append({"path": name, "sha256": hashlib.sha256(content).hexdigest(), "bytes": len(content)})
    with zipfile.ZipFile(archive) as z:
        assert all(hashlib.sha256(z.read(r["path"])).hexdigest() == r["sha256"] for r in records)
    result = {"created_at": datetime.now(timezone.utc).isoformat(), "archive": archive.name,
              "archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(), "files": records,
              "verified_zip_contents": True, "database_backup": "var/stage04-private (excluded)",
              "git": "not_a_git_repository"}
    with (folder / (args.name + "_manifest.json")).open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    print(json.dumps({"archive": archive.name, "files": len(records), "bytes": archive.stat().st_size,
                      "sha256": result["archive_sha256"], "verified": True}))


if __name__ == "__main__":
    main()
