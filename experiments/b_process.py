"""Start an isolated loopback B for one batch. B never sees provider keys and always runs with paid flags off."""
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import time

from runners.sandbox_client import HttpJson

ROOT = Path(__file__).resolve().parents[1]
SCRUBBED = ("DEEPSEEK_API_KEY", "C_ENABLE_PAID_RUNS", "C_MAX_COST_CNY", "OPENAI_API_KEY", "MOONSHOT_API_KEY")


class IsolatedB:
    def __init__(self, db_path: Path, log_path: Path):
        self.db_path = db_path
        self.log_path = log_path
        self.admin_token = secrets.token_urlsafe(32)
        self.process = None
        self.base_url = None

    def __enter__(self):
        with socket.socket() as reservation:
            reservation.bind(("127.0.0.1", 0))
            port = reservation.getsockname()[1]
        env = {k: v for k, v in os.environ.items() if k not in SCRUBBED}
        env.update(AGENTSHIELD_ADMIN_TOKEN=self.admin_token, AGENTSHIELD_DB=str(self.db_path),
                   ENABLE_PAID_RUNS="false", MAX_COST="0", PYTHONIOENCODING="utf-8")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._log = self.log_path.open("w", encoding="utf-8")
        self.process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "api.app:create_app", "--factory", "--host", "127.0.0.1",
             "--port", str(port), "--no-access-log", "--log-level", "warning"],
            cwd=ROOT, env=env, stdout=self._log, stderr=self._log,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        self.base_url = f"http://127.0.0.1:{port}"
        probe = HttpJson(self.base_url, self.admin_token, timeout=2)
        for _ in range(150):
            if self.process.poll() is not None:
                raise RuntimeError("B exited before readiness; see " + self.log_path.name)
            if probe.request("GET", "/openapi.json").http_status == 200:
                return self
            time.sleep(0.1)
        self.__exit__(None, None, None)
        raise TimeoutError("B did not become ready")

    def __exit__(self, *exc):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        self._log.close()
