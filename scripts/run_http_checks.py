"""Spawn a real loopback Uvicorn process and a separate stdlib smoke client; verify restart."""
import argparse
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile
import time

from scripts.bc_smoke_test import HttpClient, SessionClient, expect

ROOT = Path(__file__).resolve().parents[1]


def stop(process):
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def start(port, env, log):
    command = [sys.executable, "-m", "uvicorn", "api.app:create_app", "--factory", "--host", "127.0.0.1",
               "--port", str(port), "--no-access-log", "--log-level", "warning"]
    process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=log, stderr=log,
                               creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    base_url = f"http://127.0.0.1:{port}"
    probe = HttpClient(base_url, env["AGENTSHIELD_ADMIN_TOKEN"])
    for _ in range(100):
        if process.poll() is not None:
            raise RuntimeError("Independent server exited before readiness; inspect server.log.")
        try:
            if probe.request("GET", "/openapi.json")[0] == 200:
                print("Independent server ready at loopback; factory mode, access logging disabled.")
                return process
        except OSError:
            pass
        time.sleep(0.1)
    stop(process)
    raise TimeoutError("HTTP server failed to become ready")


def disconnect_check(base_url, port, manager, output):
    created = expect(manager.request("POST", "/api/v1/sessions", {"tenant_id": "tcp-disconnect-test"}), 201)
    sid = created["session"]["session_id"]
    agent = SessionClient(base_url, sid, created["session_token"])
    case = expect(agent.tool("get_case", {}))
    order = expect(agent.tool("get_order", {"order_id": case["candidate_order_ids"][0]}))
    body = {"order_id": order["order_id"], "items": [{"item_id": order["items"][0]["item_id"], "quantity": 1}],
            "confirmation_message_id": case["messages"][0]["message_id"], "expected_version": 1, "reason": "TCP close before reading response"}
    payload = json.dumps(body).encode("utf-8")
    header = (f"POST /api/v1/sessions/{sid}/tools/submit_refund HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\n"
              f"Authorization: Bearer {created['session_token']}\r\nContent-Type: application/json\r\n"
              f"Content-Length: {len(payload)}\r\nIdempotency-Key: tcp-close-key\r\nX-Call-ID: tcp-close-call\r\nConnection: close\r\n\r\n")
    with socket.create_connection(("127.0.0.1", port), timeout=5) as connection:
        connection.sendall(header.encode("ascii") + payload)
        connection.shutdown(socket.SHUT_WR)
        # Deliberately never recv/read any response bytes. No production fault switch.
    for _ in range(50):
        history = expect(agent.tool("get_refund_history", {"order_id": order["order_id"], "idempotency_key": "tcp-close-key"}))
        if history["request_status"] == "committed":
            break
        time.sleep(0.1)
    assert history["request_status"] == "committed", "Complete sent request was not observed committed after TCP close"
    replay = expect(agent.tool("submit_refund", body, "tcp-close-key"))
    assert replay["transaction_id"] == history["transaction_id"] and replay["amount_cents"] == 333
    evidence = expect(manager.request("GET", f"/api/v1/admin/sessions/{sid}/evidence"))
    assert len(evidence["refunds"]) == len(evidence["ledger"]) == 1
    assert all(event["client_receipt"] == "unknown" for event in evidence["events"])
    (output / "tcp_disconnect_evidence.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"actual_tcp_disconnect": "pass", "response_bytes_read": 0, "refund_cents": 333,
                      "refund_count": 1, "ledger_count": 1, "same_key_recovery": True}))


def label_check(manager, base_url):
    # Only controlled metadata propagation; no provider/model/API call is made or asserted.
    for source in ("scripted_test", "mock_agent", "observed_agent_execution"):
        created = expect(manager.request("POST", "/api/v1/sessions", {"tenant_id": "label-only", "execution_source": source}), 201)
        sid = created["session"]["session_id"]
        agent = SessionClient(base_url, sid, created["session_token"])
        expect(agent.tool("get_case", {}))
        evidence = expect(manager.request("GET", f"/api/v1/admin/sessions/{sid}/evidence"))
        assert evidence["sources"]["execution_source"] == source
        assert all(event["sources"]["execution_source"] == source for event in evidence["events"])
    print(json.dumps({"execution_source_label_propagation": "pass", "labels_checked": 3,
                      "model_calls": 0, "real_execution_proof": False}))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=os.environ.get("AGENTSHIELD_HTTP_OUTPUT", "artifacts/http_checks/run-" + secrets.token_hex(6)))
    args = parser.parse_args()
    output = (ROOT / args.output_dir).resolve()
    output.mkdir(parents=True, exist_ok=False)
    print("HTTP evidence directory: " + str(output.relative_to(ROOT)))
    (ROOT / "var").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="http-check-", dir=ROOT / "var") as temp:
        env = dict(os.environ, AGENTSHIELD_ADMIN_TOKEN=secrets.token_urlsafe(32),
                   AGENTSHIELD_DB=str(Path(temp) / "http.sqlite3"), ENABLE_PAID_RUNS="false", MAX_COST="0", PYTHONIOENCODING="utf-8")
        with socket.socket() as reservation:
            reservation.bind(("127.0.0.1", 0))
            port = reservation.getsockname()[1]
        base_url = f"http://127.0.0.1:{port}"
        with (output / "server.log").open("w", encoding="utf-8") as log:
            process = start(port, env, log)
            try:
                command = [sys.executable, "-I", str(ROOT / "scripts/bc_smoke_test.py"), "--base-url", base_url, "--output-dir", str(output)]
                completed = subprocess.run(command, cwd=temp, env=env, capture_output=True, text=True, encoding="utf-8", timeout=60)
                print(completed.stdout)
                if completed.returncode:
                    print(completed.stderr.replace(env["AGENTSHIELD_ADMIN_TOKEN"], "[REDACTED]"))
                    raise RuntimeError(f"Independent HTTP smoke client exited {completed.returncode}")
                manager = HttpClient(base_url, env["AGENTSHIELD_ADMIN_TOKEN"])
                created = expect(manager.request("POST", "/api/v1/sessions", {"tenant_id": "restart-test"}), 201)
                agent = SessionClient(base_url, created["session"]["session_id"], created["session_token"])
                case = expect(agent.tool("get_case", {}))
                order = expect(agent.tool("get_order", {"order_id": case["candidate_order_ids"][0]}))
                body = {"order_id": order["order_id"], "items": [{"item_id": order["items"][0]["item_id"], "quantity": 1}],
                        "confirmation_message_id": case["messages"][0]["message_id"], "expected_version": 1, "reason": "process restart test"}
                first = expect(agent.tool("submit_refund", body, "restart-key"))
                review_body = {"category": "restart-check", "missing_facts": ["human review pending"],
                               "evidence_message_ids": [case["messages"][0]["message_id"]], "expected_version": 2}
                review = expect(agent.tool("submit_human_review", review_body, "restart-review-key"))
            finally:
                stop(process)
            process = start(port, env, log)
            try:
                replay = expect(agent.tool("submit_refund", body, "restart-key"))
                assert first == replay and replay["amount_cents"] == 333
                assert expect(agent.tool("submit_human_review", review_body, "restart-review-key")) == review
                evidence = expect(manager.request("GET", f"/api/v1/admin/sessions/{agent.sid}/evidence"))
                assert len(evidence["ledger"]) == len(evidence["refunds"]) == 1
                assert evidence["human_reviews"] == [review]
                assert evidence["case_context"] == created["case_context"]
                export = subprocess.run([sys.executable, "-m", "scripts.export_evidence", "--base-url", base_url,
                                         "--session-id", agent.sid, "--output-dir", str(Path(temp) / "export")],
                                        cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8", timeout=20)
                assert export.returncode == 0, "Read-only export command failed"
                exported = json.loads((Path(temp) / "export/evidence.json").read_text(encoding="utf-8"))
                assert exported["ledger"] == evidence["ledger"] and exported["refunds"] == evidence["refunds"]
                print(json.dumps({"process_restart": "pass", "recovered_original_transaction": True,
                                  "ledger_entries": 1, "refund_cents": 333, "readonly_export": "pass",
                                  "smoke_client_isolated_python": True, "human_review_recovered": True,
                                  "frozen_case_context_recovered": True}))
                disconnect_check(base_url, port, manager, output)
                label_check(manager, base_url)
            finally:
                stop(process)


if __name__ == "__main__":
    main()
