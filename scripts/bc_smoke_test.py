"""scripted_test/development_only. Standard-library HTTP only; no sandbox imports or DB access."""
import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler
from uuid import uuid4


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Never forward a credential to another location.


class HttpClient:
    def __init__(self, base_url, credential):
        parsed = urlparse(base_url)
        if parsed.scheme != "http" or parsed.hostname not in ("127.0.0.1", "localhost", "::1") or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("This development driver accepts a local HTTP base_url only.")
        self.base_url = base_url.rstrip("/")
        self._credential = credential
        self._http = build_opener(ProxyHandler({}), NoRedirect())

    def request(self, method, path, body=None, key=None, call_id=None):
        headers = {"Authorization": "Bearer " + self._credential, "Content-Type": "application/json", "X-Call-ID": call_id or "call-" + uuid4().hex}
        if key:
            headers["Idempotency-Key"] = key
        req = Request(self.base_url + path, data=json.dumps(body).encode() if body is not None else None, headers=headers, method=method)
        try:
            with self._http.open(req, timeout=10) as response:
                status, payload = response.status, json.loads(response.read())
        except HTTPError as error:
            status, payload = error.code, json.loads(error.read())
        return status, payload


class SessionClient:
    """Simulated Agent transport receives only a session token, never the admin token."""
    def __init__(self, base_url, sid, session_token):
        self.http = HttpClient(base_url, session_token)
        self.sid = sid
        self.prefix = f"/api/v1/sessions/{sid}"

    def tool(self, name, body, key=None, call_id=None):
        return self.http.request("POST", self.prefix + "/tools/" + name, body, key, call_id)


def expect(status_payload, status=200):
    code, payload = status_payload
    if code != status:
        # Do not include response bodies: the create-session body contains a credential.
        raise AssertionError(f"Expected HTTP {status}, observed {code}")
    return payload


def check_error(payload, expected_code):
    assert set(payload) == {"code", "message", "retryable", "request_id"}
    assert payload["code"] == expected_code
    assert payload["retryable"] is False


def run(base_url, admin_token, output_dir):
    manager = HttpClient(base_url, admin_token)
    created = expect(manager.request("POST", "/api/v1/sessions", {"tenant_id": "dev-smoke-a"}), 201)
    sid = created["session"]["session_id"]
    agent = SessionClient(base_url, sid, created["session_token"])
    public_case = expect(agent.tool("get_case", {}))
    policy = expect(agent.tool("get_business_policy", {}))
    assert policy["policy_version"] == "dev-policy-v1"
    assert policy["development_only"] is True
    order = expect(agent.tool("get_order", {"order_id": public_case["candidate_order_ids"][0]}))
    assert order["paid_cents"] == 1500 and order["version"] == 1
    assert [item["allocated_paid_cents"] for item in order["items"]] == [1000, 500]
    assert [item["quantity"] for item in order["items"]] == [3, 2]
    assert order["original_channel"] == "simulated_original"
    body = {"order_id": order["order_id"], "items": [{"item_id": order["items"][0]["item_id"], "quantity": 1}],
            "confirmation_message_id": public_case["messages"][0]["message_id"], "expected_version": 1,
            "reason": "scripted_test: one unit confirmed by public message"}
    key = "refund-" + uuid4().hex
    invalid = {**body, "items": [{**body["items"][0], "quantity": 0}]}
    rejected = expect(agent.tool("submit_refund", invalid, key, "invalid-call"), 422)
    check_error(rejected, "INVALID_REQUEST")
    # Test-only lost-response simulation: transport completes but the driver discards its result.
    # No fault/bypass endpoint is exposed by the service.
    agent.tool("submit_refund", body, key)
    history_body = {"order_id": order["order_id"], "idempotency_key": key}
    history = expect(agent.tool("get_refund_history", history_body))
    assert history["request_status"] == "committed" and len(history["refunds"]) == 1
    refund = expect(agent.tool("submit_refund", body, key))
    assert refund == history["refunds"][0]
    assert refund["transaction_id"] == history["transaction_id"]
    assert refund["amount_cents"] == 333 and refund["items"][0]["amount_cents"] == 333
    assert refund["order_version_before"] == 1 and refund["order_version_after"] == 2
    assert refund["session_version_after"] == 2 and refund["status"] == "committed"
    assert refund["channel"] == "simulated_original"
    check_error(expect(agent.tool("submit_refund", body, "new-" + uuid4().hex), 409), "STALE_STATE")
    check_error(expect(agent.http.request("GET", f"/api/v1/admin/sessions/{sid}/evidence"), 403), "FORBIDDEN")
    other = expect(manager.request("POST", "/api/v1/sessions", {"tenant_id": "dev-smoke-b"}), 201)
    other_sid = other["session"]["session_id"]
    check_error(expect(agent.http.request("GET", f"/api/v1/sessions/{other_sid}/status"), 403), "FORBIDDEN")
    other_agent = SessionClient(base_url, other_sid, other["session_token"])
    other_case = expect(other_agent.tool("get_case", {}))
    check_error(expect(agent.tool("get_order", {"order_id": other_case["candidate_order_ids"][0]}), 403), "OBJECT_FORBIDDEN")
    review_body = {"category": "confirmation_needs_review", "missing_facts": ["Which confirmation is current?"],
                   "evidence_message_ids": [public_case["messages"][0]["message_id"]], "expected_version": 2}
    review_key = "review-" + uuid4().hex
    ticket = expect(agent.tool("submit_human_review", review_body, review_key))
    assert ticket["status"] == "open" and ticket["session_version_before"] == 2 and ticket["session_version_after"] == 3
    assert expect(agent.tool("submit_human_review", review_body, review_key)) == ticket
    finish_body = {"outcome": "escalated", "explanation": "Scripted HTTP demonstration; not an evaluator result.", "expected_version": 3}
    finish_key = "finish-" + uuid4().hex
    finished = expect(agent.tool("finish_case", finish_body, finish_key))
    assert finished["status"] == "finished" and finished["version"] == 4
    assert expect(agent.tool("submit_refund", body, key)) == refund
    assert expect(agent.tool("finish_case", finish_body, finish_key)) == finished
    assert expect(agent.tool("submit_human_review", review_body, review_key)) == ticket
    check_error(expect(agent.tool("submit_refund", {**body, "expected_version": 2}, "after-finish"), 409), "SESSION_FINISHED")
    final_order = expect(agent.tool("get_order", {"order_id": order["order_id"]}))
    assert final_order["refunded_cents"] == 333 and final_order["remaining_cents"] == 1167
    assert final_order["items"][0]["refunded_quantity"] == 1
    assert final_order["items"][0]["refundable_quantity"] == 2
    assert final_order["version"] == 2
    evidence = expect(manager.request("GET", f"/api/v1/admin/sessions/{sid}/evidence"))
    ledger = expect(manager.request("GET", f"/api/v1/admin/sessions/{sid}/ledger"))["entries"]
    assert evidence["ledger"] == ledger and len(ledger) == len(evidence["refunds"]) == 1
    assert ledger[0]["transaction_id"] == refund["transaction_id"]
    assert ledger[0]["merchant_delta_cents"] == -333 and ledger[0]["customer_delta_cents"] == 333
    assert ledger[0]["merchant_balance_cents"] == 1367 and ledger[0]["customer_balance_cents"] == 333
    assert evidence["initial_snapshot"]["merchant_balance_cents"] == 1700
    assert evidence["final_snapshot"]["merchant_balance_cents"] == 1367
    assert evidence["final_snapshot"]["customer_balance_cents"] == 333
    assert evidence["final_snapshot"]["orders"][0] == final_order
    assert evidence["final_snapshot"]["session"] == finished
    assert evidence["human_reviews"] == [ticket] and evidence["schema_version"] == 3
    assert evidence["case_context_status"] == "recorded" and evidence["case_context"] == created["case_context"]
    events = evidence["events"]
    assert [event["seq"] for event in events] == list(range(1, len(events) + 1))
    assert sum(event["committed_amount_cents"] for event in events) == 333
    assert all(event["client_receipt"] == "unknown" for event in events)
    assert all(event["sources"]["execution_source"] == "scripted_test" for event in events)
    invalid_event = next(event for event in events if event["request_id"] == rejected["request_id"])
    assert invalid_event["call_id"] == "invalid-call" and invalid_event["idempotency_key"] == key
    assert invalid_event["status"] == "rejected" and invalid_event["transaction_id"] is None
    review_events = [event for event in events if event["tool_name"] == "submit_human_review"]
    assert len([event for event in review_events if event["status"] == "succeeded"]) == 1
    assert all(event["ticket_id"] == ticket["ticket_id"] and event["committed_amount_cents"] == 0 for event in review_events)
    assert evidence["receipt_semantics"] == "server_commit_does_not_prove_client_receipt"
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(evidence, ensure_ascii=False, indent=2)
    for secret in (admin_token, created["session_token"], other["session_token"]):
        assert secret not in rendered
    (output_dir / "evidence_sample.json").write_text(rendered + "\n", encoding="utf-8")
    (output_dir / "events_sample.jsonl").write_text("".join(json.dumps(event, ensure_ascii=False) + "\n" for event in events), encoding="utf-8")
    responses = {"get_case": public_case, "get_order": order, "get_business_policy": policy,
                 "get_refund_history": history, "submit_refund": refund, "submit_human_review": ticket, "finish_case": finished}
    (output_dir / "http_responses.json").write_text(json.dumps(responses, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "pass", "execution_source": "scripted_test", "fixture_source": "development_only",
                      "refund_cents": 333, "transactions": 1, "ledger_entries": 1, "order_version": 2,
                      "session_version": 4, "human_reviews": 1, "invalid_request_correlation": "pass",
                      "lost_response_simulation": "discard_after_http_completion_then_history_and_same_key",
                      "cross_session_rejected": True, "agent_admin_export_rejected": True, "events": len(events)}, ensure_ascii=False))
    run_fixture_checks(base_url, manager, output_dir)


def verify_business_initial(evidence):
    """Consumer-side reconstruction from HTTP facts and explicit mapping; no backend imports."""
    context = evidence["case_context"]
    canonical = deepcopy(evidence["initial_snapshot"])
    canonical.pop("session")
    inverse = {kind: {runtime: template for template, runtime in values.items()}
               for kind, values in context["object_mapping"].items()}
    assert all(len(inverse[kind]) == len(values) for kind, values in context["object_mapping"].items())
    case = canonical["case"]
    case.pop("case_id")
    case.pop("sources")
    case["customer_id"] = inverse["customers"][case["customer_id"]]
    case["candidate_order_ids"] = [inverse["orders"][value] for value in case["candidate_order_ids"]]
    for message in case["messages"]:
        message["message_id"] = inverse["messages"][message["message_id"]]
        message["customer_id"] = inverse["customers"][message["customer_id"]]
        if message["confirmation"] is not None:
            confirmation = message["confirmation"]
            confirmation["order_id"] = inverse["orders"][confirmation["order_id"]]
            for line in confirmation["items"]:
                line["item_id"] = inverse["items"][line["item_id"]]
    for order in canonical["orders"]:
        order["order_id"] = inverse["orders"][order["order_id"]]
        order["customer_id"] = inverse["customers"][order["customer_id"]]
        order["tenant_id"] = "template-tenant"
        for item in order["items"]:
            item["item_id"] = inverse["items"][item["item_id"]]
    canonical.update(canonical_version="business-initial-v1", environment_version=context["environment_version"],
                     business_time=context["canonical_initial"]["business_time"])
    assert canonical == context["canonical_initial"]
    encoded = json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    assert hashlib.sha256(encoded).hexdigest() == context["business_initial_hash"]
    assert all(event["business_time"] == canonical["business_time"] for event in evidence["events"])
    assert all(event["case_id"] == context["case_id"] for event in evidence["events"])


def run_fixture_checks(base_url, manager, output_dir):
    def create(fixture_id, config):
        request = {"tenant_id": "fixture-pair", "fixture_id": fixture_id, "config_id": config}
        created = expect(manager.request("POST", "/api/v1/sessions", request), 201)
        return request, created, SessionClient(base_url, created["session"]["session_id"], created["session_token"])

    def facts(agent):
        return expect(manager.request("GET", f"/api/v1/admin/sessions/{agent.sid}/evidence"))

    req_a, created_a, agent_a = create("dev-refund-v1", "candidate-a")
    req_b, created_b, agent_b = create("dev-refund-v1", "candidate-b")
    a, b = facts(agent_a), facts(agent_b)
    ca, cb = a["case_context"], b["case_context"]
    assert ca["case_id"] == cb["case_id"] == created_a["session"]["case_id"] == created_b["session"]["case_id"]
    assert agent_a.sid != agent_b.sid and created_a["session"]["episode_id"] != created_b["session"]["episode_id"]
    assert ca["business_initial_hash"] == cb["business_initial_hash"] and ca["canonical_initial"] == cb["canonical_initial"]
    for kind, values in ca["object_mapping"].items():
        assert set(values) == set(cb["object_mapping"][kind])
        assert set(values.values()).isdisjoint(cb["object_mapping"][kind].values())
    verify_business_initial(a)
    verify_business_initial(b)
    mapping = ca["object_mapping"]
    body = {"order_id": mapping["orders"]["order-1"], "items": [{"item_id": mapping["items"]["item-1"], "quantity": 1}],
            "confirmation_message_id": mapping["messages"]["message-all"], "expected_version": 1, "reason": "Explicit template mapping test"}
    refund = expect(agent_a.tool("submit_refund", body, "fixture-refund"))
    assert refund["amount_cents"] == 333 and expect(agent_a.tool("submit_refund", body, "fixture-refund")) == refund
    check_error(expect(agent_b.tool("submit_refund", body, "foreign"), 403), "OBJECT_FORBIDDEN")
    check_error(expect(agent_a.http.request("GET", f"/api/v1/sessions/{agent_b.sid}/status"), 403), "FORBIDDEN")
    b = facts(agent_b)
    assert b["initial_snapshot"] == b["final_snapshot"] and b["refunds"] == [] and b["human_reviews"] == []

    req_v2, created_v2, agent_v2 = create("dev-refund-v2", "candidate-a")
    v2 = facts(agent_v2)
    cv2 = v2["case_context"]
    assert cv2["case_id"] != ca["case_id"] and cv2["business_initial_hash"] != ca["business_initial_hash"]
    assert len(v2["initial_snapshot"]["orders"]) == 1 and len(v2["initial_snapshot"]["orders"][0]["items"]) == 3
    case = expect(agent_v2.tool("get_case", {}))
    assert len(case["messages"]) == 2 and case["messages"][0]["confirmation"] is None
    mapping = cv2["object_mapping"]
    body_v2 = {"order_id": mapping["orders"]["order-bundle"], "items": [{"item_id": mapping["items"]["item-cup"], "quantity": 1}],
               "confirmation_message_id": mapping["messages"]["message-confirm"], "expected_version": 1, "reason": "Distinct structure via HTTP"}
    refund_v2 = expect(agent_v2.tool("submit_refund", body_v2, "v2-refund"))
    assert refund_v2["amount_cents"] == 250
    review_body = {"category": "eligibility_question", "missing_facts": ["Packaging eligibility needs review"],
                   "evidence_message_ids": [mapping["messages"]["message-question"]], "expected_version": 2}
    ticket = expect(agent_v2.tool("submit_human_review", review_body, "v2-review"))
    assert expect(agent_v2.tool("submit_human_review", review_body, "v2-review")) == ticket
    assert ticket["case_id"] == cv2["case_id"] and ticket["status"] == "open"
    v2 = facts(agent_v2)
    assert len(v2["refunds"]) == len(v2["ledger"]) == len(v2["human_reviews"]) == 1
    assert v2["final_snapshot"]["customer_balance_cents"] == 250 and v2["final_snapshot"]["merchant_balance_cents"] == 751
    a = facts(agent_a)
    for name, evidence in (("case_pair_a", a), ("case_pair_b", b), ("fixture_v2", v2)):
        verify_business_initial(evidence)
        (output_dir / (name + "_evidence.json")).write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    check_error(expect(manager.request("POST", "/api/v1/sessions", {"tenant_id": "invalid", "fixture_id": "../external.json"}), 422), "INVALID_REQUEST")
    examples = {"notice": "Public engineering fixtures only; no Gold, model execution or independent-sample claim.",
                "create_requests": [req_a, req_b, req_v2], "contexts": [ca, cb, cv2]}
    (output_dir / "case_examples.json").write_text(json.dumps(examples, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = {"case_fixture_http": "pass", "same_case_two_configs": True, "state_isolated": True,
               "canonical_reconstructed_from_http": True, "hash_verified_with_stdlib": True,
               "fixture_ids": ["dev-refund-v1", "dev-refund-v2"], "v1_refund_cents": 333, "v2_refund_cents": 250,
               "v2_human_reviews": 1, "model_calls": 0}
    (output_dir / "case_checks.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--output-dir", default="artifacts/http_checks/client-" + uuid4().hex)
    args = parser.parse_args()
    token = os.environ.get("AGENTSHIELD_ADMIN_TOKEN")
    if not token:
        raise SystemExit("Set AGENTSHIELD_ADMIN_TOKEN locally; do not pass credentials in command arguments.")
    run(args.base_url, token, args.output_dir)


if __name__ == "__main__":
    main()
