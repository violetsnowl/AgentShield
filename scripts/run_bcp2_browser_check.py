"""Real B + observer + Edge check for a generated schema-v2 opening-history case."""
import argparse
import json
from pathlib import Path
import secrets
import socket
import subprocess
import tempfile

from api.app import create_app
from scripts.bc_smoke_test import HttpClient, SessionClient, expect
from scripts.run_workbench import running
from workbench.app import create_observer

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    output = (ROOT / args.output_dir).resolve()
    allowed = (ROOT / "artifacts/b_case_generator").resolve()
    if not output.is_relative_to(allowed):
        raise SystemExit("Output must stay under artifacts/b_case_generator")
    output.mkdir(parents=True, exist_ok=False)
    token, grant = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    with tempfile.TemporaryDirectory(prefix="bcp2-browser-", dir=ROOT / "var") as folder:
        b_app = create_app(Path(folder) / "b.sqlite3", token)
        with running(b_app) as b_url:
            manager = HttpClient(b_url, token)
            created = expect(manager.request("POST", "/api/v1/sessions", {
                "tenant_id": "workbench-development",
                "fixture_id": "bcp2-l1-whole-low-04",
                "experiment_id": "bcp2-browser-check",
                "config_id": "scripted-browser-check",
                "execution_source": "scripted_test",
            }), 201)
            sid = created["session"]["session_id"]
            agent = SessionClient(b_url, sid, created["session_token"])
            case = expect(agent.tool("get_case", {}))
            order = expect(agent.tool("get_order", {"order_id": case["candidate_order_ids"][0]}))
            line = order["items"][0]
            assert line["refunded_quantity"] == 1 and line["refundable_quantity"] == 2 and order["version"] == 2
            message = next(row for row in case["messages"] if row["confirmation"])
            refund = expect(agent.tool("submit_refund", {
                "order_id": order["order_id"],
                "items": [{"item_id": line["item_id"], "quantity": 1}],
                "confirmation_message_id": message["message_id"],
                "expected_version": order["version"],
                "reason": "B-CP2 browser evidence check",
            }, "bcp2-browser-refund"))
            before = expect(manager.request("GET", f"/api/v1/admin/sessions/{sid}/evidence"))
            assert len(before["refunds"]) == len(before["ledger"]) == 1
            assert before["initial_snapshot"]["customer_balance_cents"] > 0
            assert before["refunds"][0]["amount_cents"] == refund["amount_cents"]

            with socket.socket() as reservation:
                reservation.bind(("127.0.0.1", 0))
                port = reservation.getsockname()[1]
            origin = f"http://127.0.0.1:{port}"
            observer = create_observer(b_url, token, grant, origin=origin)
            with running(observer, port):
                config = {
                    "origin": origin, "grant": grant, "forbidden": [token],
                    "output": str(output), "sessionId": sid,
                    "caseId": created["session"]["case_id"],
                    "currentRefundCents": refund["amount_cents"],
                    "openingCustomerCents": before["initial_snapshot"]["customer_balance_cents"],
                }
                result = subprocess.run(
                    ["node", str(ROOT / "frontend/tests/bcp2-browser.mjs")],
                    input=json.dumps(config), capture_output=True, text=True,
                    encoding="utf-8", cwd=ROOT, timeout=90,
                )
                safe = (result.stdout + result.stderr).replace(token, "[REDACTED]").replace(grant, "[REDACTED]")
                (output / "browser.log").write_text(safe, encoding="utf-8")
                print(safe)
                if result.returncode:
                    raise SystemExit(result.returncode)
            after = expect(manager.request("GET", f"/api/v1/admin/sessions/{sid}/evidence"))
            for key in ("events", "refunds", "ledger", "human_reviews", "initial_snapshot", "final_snapshot"):
                assert before[key] == after[key]
    for path in output.rglob("*"):
        if path.is_file():
            text = path.read_text(encoding="utf-8", errors="ignore")
            assert token not in text and grant not in text
    print(json.dumps({
        "generated_schema_v2_browser": "pass",
        "fixture_id": "bcp2-l1-whole-low-04",
        "opening_history_visible": True,
        "episode_refund_only_in_committed_total": True,
        "observer_read_only": True,
        "model_calls": 0,
        "real_payment_calls": 0,
    }))


if __name__ == "__main__":
    main()
