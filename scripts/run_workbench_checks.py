"""Real loopback B/observer + isolated Edge browser, with credential-free evidence outputs."""
import argparse
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import tempfile
from unittest.mock import patch

from api.app import create_app
from scripts.bc_smoke_test import HttpClient, SessionClient, expect
from scripts.run_workbench import running, seed_development
from workbench.app import create_observer

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--phase", choices=("core", "final"), default="final")
    parser.add_argument("--suite", choices=("stage03", "stage04"), default="stage03")
    parser.add_argument("--expect-vulnerable", action="store_true", help="Record pre-fix reproduction; not a passing release check")
    parser.add_argument("--playwright-module", default=os.environ.get("PLAYWRIGHT_MODULE_PATH"))
    args = parser.parse_args()
    output = (ROOT / args.output_dir).resolve()
    if not any(output.is_relative_to(ROOT / f"artifacts/pro_bd_sprint/{stage}") for stage in ("03", "04", "05")):
        raise SystemExit("QA outputs must be under stage 03/04/05 artifacts")
    output.mkdir(parents=True, exist_ok=False)
    token, grant = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    with tempfile.TemporaryDirectory(prefix="workbench-http-", dir=ROOT / "var") as folder:
        app = create_app(Path(folder) / "qa.sqlite3", token)
        with running(app) as b_url:
            ids = seed_development(b_url, token, "workbench-development")
            assert len(ids) == 2
            assert seed_development(b_url, token, "workbench-development") == []
            manager = HttpClient(b_url, token)
            fixtures = expect(manager.request("GET", "/api/v1/admin/fixtures"))
            (output / "fixtures.json").write_text(json.dumps(fixtures, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            sessions = expect(manager.request("GET", "/api/v1/admin/sessions?tenant_id=workbench-development&limit=1"))
            (output / "sessions-page.json").write_text(json.dumps(sessions, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            first_page = expect(manager.request("GET", f"/api/v1/admin/sessions/{ids[0]}/events?limit=4"))
            second_page = expect(manager.request("GET", f"/api/v1/admin/sessions/{ids[0]}/events?limit=4&after_seq={first_page['last_seq']}"))
            (output / "event-pages.json").write_text(json.dumps([first_page, second_page], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            initial = {}
            for sid in ids:
                evidence = expect(manager.request("GET", f"/api/v1/admin/sessions/{sid}/evidence"))
                assert len(evidence["ledger"]) == len(evidence["refunds"]) == 1
                fixture = evidence["case_context"]["fixture_id"]
                initial[sid] = evidence
                for suffix in ("evidence", "events", "ledger"):
                    payload = expect(manager.request("GET", f"/api/v1/admin/sessions/{sid}/{suffix}"))
                    (output / f"{fixture}_{suffix}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            if args.suite == "stage04" and not args.expect_vulnerable:
                # QA-only fault in a separate real HTTP session. Never alter the two seeded runs.
                created = expect(manager.request("POST", "/api/v1/sessions", {
                    "tenant_id": "workbench-development", "fixture_id": "dev-refund-v1",
                    "execution_source": "scripted_test", "config_id": "fault-injection-test-only"}), 201)
                sid = created["session"]["session_id"]
                agent = SessionClient(b_url, sid, created["session_token"])
                case = expect(agent.tool("get_case", {}))
                order = expect(agent.tool("get_order", {"order_id": case["candidate_order_ids"][0]}))
                message = next(m for m in case["messages"] if m["confirmation"] is not None)
                body = {"order_id": order["order_id"], "items": [{"item_id": order["items"][0]["item_id"], "quantity": 1}],
                        "confirmation_message_id": message["message_id"], "expected_version": 1, "reason": "QA-only controlled storage failure"}
                with patch.object(app.state.store, "_insert_ledger", side_effect=RuntimeError("QA-only failure")):
                    expect(agent.tool("submit_refund", body, "qa-error-only"), 500)
                failure = expect(manager.request("GET", f"/api/v1/admin/sessions/{sid}/evidence"))
                assert failure["events"][-1]["status"] == "error" and not failure["refunds"] and not failure["ledger"]
                initial[sid] = failure
                (output / "fault-injection-evidence.json").write_text(json.dumps(failure, ensure_ascii=False, indent=2), encoding="utf-8")
            with socket.socket() as reservation:
                reservation.bind(("127.0.0.1", 0))
                port = reservation.getsockname()[1]
            origin = f"http://127.0.0.1:{port}"
            observer = create_observer(b_url, token, grant, origin=origin)
            with running(observer, port):
                config = {"origin": origin, "grant": grant, "forbidden": [token], "output": str(output),
                          "phase": args.phase, "playwrightModule": args.playwright_module,
                          "sessions": ids, "root": str(ROOT), "expectVulnerable": args.expect_vulnerable}
                # Credentials only cross a private pipe to the trusted QA driver, never argv,
                # files, logs or page.evaluate. Only the separate observer grant reaches UI.
                browser_script = "browser.mjs" if args.suite == "stage03" else "stage04-browser.mjs"
                result = subprocess.run(["node", str(ROOT / "frontend/tests" / browser_script)], input=json.dumps(config),
                                        capture_output=True, encoding="utf-8", cwd=ROOT, timeout=180)
                safe = (result.stdout + result.stderr).replace(token, "[REDACTED]").replace(grant, "[REDACTED]")
                (output / "browser.log").write_text(safe, encoding="utf-8")
                print(safe)
                if result.returncode:
                    raise SystemExit(result.returncode)
            for sid, before in initial.items():
                after = expect(manager.request("GET", f"/api/v1/admin/sessions/{sid}/evidence"))
                for key in ("events", "refunds", "ledger", "human_reviews", "initial_snapshot", "final_snapshot"):
                    assert after[key] == before[key], "Observer/browser altered a seeded run"
            if args.phase == "final" and args.suite == "stage03":
                created = json.loads((output / "created-session-observer.json").read_text(encoding="utf-8"))
                new_run = expect(manager.request("GET", f"/api/v1/admin/sessions/{created['session']['session_id']}/evidence"))
                assert not new_run["events"] and not new_run["ledger"] and not new_run["refunds"]
                assert new_run["case_context"]["business_initial_hash"] == initial[ids[0]]["case_context"]["business_initial_hash"]
                assert new_run["final_snapshot"]["session"]["episode_id"] != initial[ids[0]]["final_snapshot"]["session"]["episode_id"]
            for path in output.rglob("*"):
                if path.is_file() and path.suffix in (".json", ".log"):
                    content = path.read_text(encoding="utf-8")
                    assert token not in content and grant not in content
            print(json.dumps({"real_B_HTTP": "pass", "two_fixtures": True, "browser_is_observer_only": True,
                              "original_transactions_unchanged": True, "seeding_restart_idempotent": True,
                              "model_calls": 0, "real_payment_calls": 0}))


if __name__ == "__main__":
    main()
