"""Record a real subprocess command, sanitized output and exit code in one JSON file."""
import argparse
from datetime import datetime, timezone
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="artifacts/b_bootstrap")
    parser.add_argument("label")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    folder = Path(args.output_dir)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{args.label}.json"
    if path.exists() or path.with_suffix(".log").exists():
        raise SystemExit("Use a new label; never overwrite earlier test evidence.")
    command = args.command
    if command and command[0] == "--":
        command = command[1:]
    if command[0] == "python":
        command[0] = sys.executable
    started = datetime.now(timezone.utc).isoformat()
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
    def redact(value):
        for key, secret in os.environ.items():
            if ("TOKEN" in key or "SECRET" in key or "API_KEY" in key) and len(secret) >= 8:
                value = value.replace(secret, "[REDACTED]")
        return value
    output = redact(result.stdout + result.stderr)
    packages = {name: importlib.metadata.version(name) for name in ("fastapi", "pydantic", "uvicorn", "httpx", "jsonschema")}
    record = {"label": args.label, "started_at": started, "finished_at": datetime.now(timezone.utc).isoformat(),
              "command": [redact(v) for v in command], "exit_code": result.returncode,
              "status": "pass" if result.returncode == 0 else "fail", "python": sys.version,
              "platform": platform.platform(), "packages": packages, "output": output}
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    path.with_suffix(".log").write_text(output, encoding="utf-8")
    print(output)
    print(f"Recorded {path}: exit {result.returncode}")
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
