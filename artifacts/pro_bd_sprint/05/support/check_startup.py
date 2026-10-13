"""Invoke the actual CLI in a fresh reception root; grant passes to Edge via private stdin.

The callback replaces only OS browser opening, not B/observer/startup logic. It closes
the launcher after QA instead of leaving a service running. No credentials are saved.
"""
import argparse
import contextlib
import io
import json
from pathlib import Path
import socket
import subprocess
import sys
from unittest.mock import patch

from scripts.run_workbench import main


class FinishedBrowser(BaseException):
    pass


def run():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    root = Path.cwd()
    output = (root / args.output_dir).resolve()
    assert output.is_relative_to(root / "artifacts/pro_bd_sprint/05")
    output.mkdir(parents=True, exist_ok=False)
    database = root / "var" / ("stage05-startup-" + output.name + ".sqlite3")
    assert not database.exists(), "Use a fresh reception directory; never write an existing database"
    node = root / "artifacts/pro_bd_sprint/05/support/check_startup.mjs"
    previous = None
    for index in range(2):
        with socket.socket() as reservation:
            reservation.bind(("127.0.0.1", 0))
            port = reservation.getsockname()[1]
        def open_browser(url):
            nonlocal previous
            result = subprocess.run(["node", str(node)], input=json.dumps({"url": url, "output": str(output),
                                    "root": str(root), "index": index, "previous": previous}),
                                    capture_output=True, text=True, encoding="utf-8", timeout=90)
            # Neither untrusted exception text nor the grant-bearing URL is printed.
            if result.returncode:
                safe = result.stderr.replace(url, "[observer URL removed]")
                safe = safe.replace(url.split("#pair=")[-1], "[observer grant removed]")
                (output / f"browser-failure-{index}.log").write_text(safe, "utf-8")
                raise RuntimeError("Startup browser checks failed; no secret-bearing trace persisted")
            previous = json.loads(result.stdout)
            print(json.dumps(previous))
            raise FinishedBrowser()
        capture = io.StringIO()
        with patch.object(sys, "argv", ["run_workbench", "--db", str(database), "--port", str(port), "--seed-development"]), \
                patch("scripts.run_workbench.webbrowser.open", open_browser), contextlib.redirect_stdout(capture):
            try:
                main()
            except FinishedBrowser:
                pass
        text = capture.getvalue()
        assert f"Development sessions seeded: {2 if index == 0 else 0}" in text
        (output / f"startup-{index}.log").write_text(text, "utf-8")
        print(text)
        with socket.socket() as probe:
            assert probe.connect_ex(("127.0.0.1", port)) != 0, "Observer must stop after test"
    print(json.dumps({"actual_CLI_startup": True, "restart_no_reseed": True, "same_machine": True,
                      "different_operator": False, "model_calls": 0, "payment_calls": 0}))


if __name__ == "__main__":
    run()
