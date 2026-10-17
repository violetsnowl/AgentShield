"""Launch loopback B + authenticated observer; optional genuine scripted development data."""
import argparse
from contextlib import contextmanager
from pathlib import Path
import secrets
import socket
import threading
import time
import webbrowser

import uvicorn

from api.app import create_app
from scripts.bc_smoke_test import HttpClient, SessionClient, expect
from workbench.app import create_observer

ROOT = Path(__file__).resolve().parents[1]


@contextmanager
def running(app, port=0):
    sock = socket.socket()
    sock.bind(("127.0.0.1", port))
    actual_port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=actual_port,
                                         access_log=False, log_level="critical"))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 10
        while not server.started:
            if not thread.is_alive() or time.monotonic() > deadline:
                raise RuntimeError("Local server did not start")
            time.sleep(0.05)
        yield f"http://127.0.0.1:{actual_port}"
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        sock.close()


def seed_development(base_url, admin_token, tenant_id):
    """Real B HTTP writes, explicitly scripted_test. No credential is returned or persisted."""
    manager = HttpClient(base_url, admin_token)
    from urllib.parse import urlencode
    existing = expect(manager.request("GET", "/api/v1/admin/sessions?" + urlencode({"tenant_id": tenant_id})))
    if existing["sessions"]:
        return []  # Restart never adds another demo transaction.
    ids = []
    for fixture in ("dev-refund-v1", "dev-refund-v2"):
        created = expect(manager.request("POST", "/api/v1/sessions", {
            "tenant_id": tenant_id, "fixture_id": fixture, "execution_source": "scripted_test",
            "experiment_id": "workbench-development", "config_id": "scripted-development-example"}), 201)
        sid = created["session"]["session_id"]
        agent = SessionClient(base_url, sid, created["session_token"])
        case = expect(agent.tool("get_case", {}))
        order = expect(agent.tool("get_order", {"order_id": case["candidate_order_ids"][0]}))
        message = next(message for message in case["messages"] if message["confirmation"] is not None)
        body = {"order_id": order["order_id"], "items": [{"item_id": order["items"][0]["item_id"], "quantity": 1}],
                "confirmation_message_id": message["message_id"], "expected_version": 1,
                "reason": "scripted_test development workbench example"}
        expect(agent.tool("submit_refund", {**body, "items": [{**body["items"][0], "quantity": 0}]}, "invalid-demo"), 422)
        refund = expect(agent.tool("submit_refund", body, "development-refund"))
        assert refund["amount_cents"] == (333 if fixture.endswith("v1") else 250)
        assert expect(agent.tool("submit_refund", body, "development-refund")) == refund
        expect(agent.tool("submit_refund", body, "development-stale"), 409)
        expect(agent.tool("get_refund_history", {"order_id": order["order_id"], "idempotency_key": "development-refund"}))
        expect(agent.tool("submit_human_review", {"category": "development-review", "missing_facts": ["A/C business review pending"],
                     "evidence_message_ids": [message["message_id"]], "expected_version": 2}, "development-ticket"))
        ids.append(sid)
    return ids


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="var/workbench.sqlite3")
    parser.add_argument("--port", type=int, default=8810)
    parser.add_argument("--tenant", default="workbench-development")
    parser.add_argument("--seed-development", action="store_true")
    parser.add_argument("--no-open", action="store_true")
    parser.add_argument("--dev-origin", default=None)
    parser.add_argument("--batch-size", type=int, default=100,
                        help="Operator-only validation override; browser cannot choose batch size")
    args = parser.parse_args()
    if not (ROOT / "frontend/dist/index.html").is_file():
        raise SystemExit("Build frontend first: cd frontend; npm ci; npm run build")
    admin_token, grant = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    with running(create_app(args.db, admin_token)) as b_url:
        if args.seed_development:
            ids = seed_development(b_url, admin_token, args.tenant)
            print(f"Development sessions seeded: {len(ids)}; model/payment calls: 0", flush=True)
        origin = f"http://127.0.0.1:{args.port}"
        observer = create_observer(b_url, admin_token, grant, origin=origin,
                                   tenant_id=args.tenant, dev_origin=args.dev_origin,
                                   bscale_batch_size=args.batch_size)
        with running(observer, args.port):
            print(f"Workbench: {origin} (local observer, one-hour access; Ctrl+C stops both services)", flush=True)
            if not args.no_open:
                # Grant is separate from B credentials; never printed or logged. Frontend removes
                # the fragment before networking, exchanges once, and retains no JS credential.
                webbrowser.open((args.dev_origin or origin) + "/#pair=" + grant)
            else:
                print("Browser approval withheld (--no-open). No unauthenticated data access.", flush=True)
            try:
                while True:
                    time.sleep(0.5)
            except KeyboardInterrupt:
                pass


if __name__ == "__main__":
    main()
