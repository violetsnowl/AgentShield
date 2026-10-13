"""Read-only lock/environment check, also runnable from the unpacked handoff root."""
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import subprocess
import sys

root = Path.cwd()
packages = {}
for line in (root / "requirements.lock").read_text("utf-8").splitlines():
    if line.strip():
        name, expected = line.split("==")
        packages[name] = version(name)
        assert packages[name] == expected, name
package = json.loads((root / "frontend/package.json").read_text("utf-8"))
frontend = {}
for name, expected in {**package["dependencies"], **package["devDependencies"]}.items():
    actual = json.loads((root / "frontend/node_modules" / name / "package.json").read_text("utf-8"))["version"]
    assert actual == expected, name
    frontend[name] = actual
subprocess.run([sys.executable, "-m", "pip", "check"], check=True)
print(json.dumps({"python": sys.version, "prefix": sys.prefix, "packages": packages,
                  "node": subprocess.check_output(["node", "--version"], text=True).strip(),
                  "npm": subprocess.check_output(["npm.cmd", "--version"], text=True).strip(),
                  "frontend_direct_packages": frontend,
                  "lock_sha256": {p: hashlib.sha256((root / p).read_bytes()).hexdigest()
                                  for p in ("requirements.lock", "frontend/package-lock.json")}}, ensure_ascii=True, indent=2))
