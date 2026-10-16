"""Observer boundary tests use isolated SQLite; never invoke a model or external service."""
import json
from pathlib import Path
import secrets
import tempfile
import time
import unittest

from fastapi.testclient import TestClient
import httpx

from api.app import create_app
from workbench.app import COOKIE, create_observer


class ObserverTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="observer-test-", dir="var")
        self.token, self.grant = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        self.b_app = create_app(Path(self.temp.name) / "test.sqlite3", self.token)
        self.b = TestClient(self.b_app)
        self.admin = {"Authorization": "Bearer " + self.token}
        self.own = self.b.post("/api/v1/sessions", json={"tenant_id": "workbench-development"}, headers=self.admin).json()
        self.other = self.b.post("/api/v1/sessions", json={"tenant_id": "private-tenant"}, headers=self.admin).json()
        self.sid = self.own["session"]["session_id"]

        def forward(request):
            result = self.b.request(request.method, str(request.url), headers=dict(request.headers), content=request.content)
            return httpx.Response(result.status_code, content=result.content)

        self.app = create_observer("http://127.0.0.1:8999", self.token, self.grant,
                                   transport=httpx.MockTransport(forward), frontend_dir=Path(self.temp.name) / "no-static")
        self.client = TestClient(self.app, base_url="http://127.0.0.1:8810", raise_server_exceptions=False)
        self.client.__enter__()
        self.headers = {"Origin": "http://127.0.0.1:8810", "X-Workbench-Request": "1"}

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.b.close()
        self.temp.cleanup()

    def pair(self):
        response = self.client.post("/observer/pair", json={"grant": self.grant}, headers=self.headers)
        self.assertEqual(response.status_code, 200)
        return response

    def test_pair_once_cookie_is_observer_only_and_expires(self):
        self.assertEqual(self.client.get("/observer/api/fixtures", headers=self.headers).status_code, 401)
        response = self.pair()
        cookie = response.headers["set-cookie"]
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=strict", cookie)
        self.assertNotIn(self.token, cookie)
        self.assertNotIn(self.own["session_token"], cookie)
        self.assertEqual(self.client.post("/observer/pair", json={"grant": self.grant}, headers=self.headers).status_code, 401)
        self.assertEqual(self.client.get("/observer/api/fixtures", headers=self.headers).status_code, 200)
        for key in self.app.state.authority.sessions:
            self.app.state.authority.sessions[key] = time.monotonic() - 1
        self.assertEqual(self.client.get("/observer/api/fixtures", headers=self.headers).status_code, 401)

    def test_expired_grant_and_validation_do_not_echo_body(self):
        response = self.client.post("/observer/pair", json={"grant": self.token, "admin_token": self.token}, headers=self.headers)
        self.assertEqual(response.status_code, 422)
        self.assertNotIn(self.token, response.text)
        self.app.state.authority.grant_until = 0
        self.assertEqual(self.client.post("/observer/pair", json={"grant": self.grant}, headers=self.headers).status_code, 401)

    def test_host_origin_csrf_and_logout(self):
        self.pair()
        for headers in ({}, {**self.headers, "Origin": "https://attacker.example"},
                        {**self.headers, "Host": "attacker.example"}, {**self.headers, "Sec-Fetch-Site": "cross-site"}):
            self.assertEqual(self.client.get("/observer/api/fixtures", headers=headers).status_code, 403)
        # Browsers omit Origin on same-origin GET; the custom header is still required.
        self.assertEqual(self.client.get("/observer/api/fixtures", headers={"X-Workbench-Request": "1", "Sec-Fetch-Site": "same-origin"}).status_code, 200)
        self.assertEqual(self.client.post("/observer/logout", headers=self.headers).status_code, 200)
        self.assertEqual(self.client.get("/observer/api/fixtures", headers=self.headers).status_code, 401)

    def test_create_is_allowlisted_and_never_returns_b_credentials(self):
        self.pair()
        for body in ({"fixture_id": "../private"}, {"fixture_id": "dev-refund-v1", "tenant_id": "private-tenant"},
                     {"fixture_id": "dev-refund-v1", "execution_source": "observed_agent_execution"}):
            self.assertEqual(self.client.post("/observer/api/sessions", json=body, headers=self.headers).status_code, 422)
        for fixture in ("dev-refund-v1", "dev-refund-v2"):
            response = self.client.post("/observer/api/sessions", json={"fixture_id": fixture}, headers=self.headers)
            self.assertEqual(response.status_code, 201)
            self.assertNotIn("session_token", response.text)
            self.assertNotIn(self.token, response.text)
            self.assertEqual(response.json()["session"]["sources"]["execution_source"], "scripted_test")
            evidence = self.b_app.state.store.evidence(response.json()["session"]["session_id"])
            self.assertEqual(evidence["events"], [])
            self.assertEqual(evidence["ledger"], [])

    def test_scope_and_no_tool_or_generic_proxy(self):
        self.pair()
        response = self.client.get("/observer/api/sessions", headers=self.headers)
        self.assertEqual([row["session_id"] for row in response.json()["sessions"]], [self.sid])
        for suffix in ("events", "ledger", "evidence"):
            response = self.client.get(f"/observer/api/sessions/{self.other['session']['session_id']}/{suffix}", headers=self.headers)
            self.assertEqual(response.status_code, 404)
            self.assertNotIn(self.other["session_token"], response.text)
        for path in (f"/observer/api/sessions/{self.sid}/tools/submit_refund", "/observer/api/admin/anything", "/api/v1/admin/fixtures"):
            self.assertIn(self.client.post(path, json={}, headers=self.headers).status_code, (404, 405))

    def test_ac_delivery_results_are_authenticated_read_only_and_identity_linked(self):
        self.assertEqual(self.client.get("/observer/api/integration-runs", headers=self.headers).status_code, 401)
        self.pair()
        before = self.b_app.state.store.evidence(self.sid)
        response = self.client.get("/observer/api/integration-runs", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        rows = response.json()["runs"]
        self.assertGreaterEqual(len(rows), 7)
        selected = next(row for row in rows if row["execution_source"] == "observed_agent_execution")
        self.assertFalse(selected["counts_as_formal_run"])
        self.assertIn(selected["loss_status"], ("verified", "needs_review"))
        detail = self.client.get(f"/observer/api/integration-runs/{selected['run_id']}", headers=self.headers)
        self.assertEqual(detail.status_code, 200)
        payload = detail.json()
        self.assertEqual(payload["evidence"]["final_snapshot"]["session"]["session_id"], selected["session_id"])
        self.assertEqual(payload["loss_result"]["identity"]["episode_id"], selected["episode_id"])
        self.assertEqual(payload["loss_result"]["loss_status"], selected["loss_status"])
        if selected["loss_status"] == "needs_review":
            self.assertIsNone(payload["loss_result"]["net_loss_cents"])
        self.assertIsNone(payload["claim"]["payout_cents"])
        self.assertFalse(payload["claim"]["commercial_quote"])
        self.assertFalse(payload["quote_result"]["commercial_quote"])
        self.assertNotIn("api_key", detail.text.lower())
        self.assertNotIn("session_token", detail.text.lower())
        self.assertEqual(self.client.get("/observer/api/integration-runs/../secrets", headers=self.headers).status_code, 404)
        after = self.b_app.state.store.evidence(self.sid)
        for key in ("events", "refunds", "ledger", "human_reviews", "initial_snapshot", "final_snapshot"):
            self.assertEqual(before[key], after[key])

    def test_actual_catalog_admin_auth_session_list_and_event_pagination(self):
        self.assertEqual(self.b.get("/api/v1/admin/fixtures").status_code, 401)
        self.assertEqual(self.b.get("/api/v1/admin/fixtures", headers={"Authorization": "Bearer " + self.own["session_token"]}).status_code, 403)
        fixtures = self.b.get("/api/v1/admin/fixtures", headers=self.admin).json()["fixtures"]
        from sandbox.fixture import REGISTRY
        self.assertEqual([f["fixture_id"] for f in fixtures], list(REGISTRY))
        new = self.b.post("/api/v1/sessions", json={"tenant_id": "workbench-development"}, headers=self.admin).json()
        first = self.b.get("/api/v1/admin/sessions?tenant_id=workbench-development&limit=1", headers=self.admin).json()
        second = self.b.get(f"/api/v1/admin/sessions?tenant_id=workbench-development&limit=1&offset={first['next_offset']}", headers=self.admin).json()
        self.assertEqual([first["sessions"][0]["session_id"], second["sessions"][0]["session_id"]], [new["session"]["session_id"], self.sid])
        for i in range(3):
            self.b.post(f"/api/v1/sessions/{self.sid}/tools/get_case", json={}, headers={"Authorization": "Bearer " + self.own["session_token"]})
        all_events = self.b.get(f"/api/v1/admin/sessions/{self.sid}/events", headers=self.admin).json()["events"]
        self.assertEqual(len(all_events), 3)
        self.pair()
        first = self.client.get(f"/observer/api/sessions/{self.sid}/events?limit=2", headers=self.headers).json()
        second = self.client.get(f"/observer/api/sessions/{self.sid}/events?limit=2&after_seq={first['last_seq']}", headers=self.headers).json()
        self.assertEqual(first["events"] + second["events"], all_events)

    def test_observer_reads_never_add_tool_events_or_money(self):
        self.pair()
        before = self.b_app.state.store.evidence(self.sid)
        for _ in range(2):
            for resource in ("evidence", "events", "ledger"):
                response = self.client.get(f"/observer/api/sessions/{self.sid}/{resource}", headers=self.headers)
                self.assertEqual(response.status_code, 200)
                self.assertNotIn(self.token, response.text)
                self.assertNotIn(self.own["session_token"], response.text)
                self.assertEqual(response.headers["cache-control"], "no-store")
        after = self.b_app.state.store.evidence(self.sid)
        for key in ("events", "ledger", "refunds", "final_snapshot"):
            self.assertEqual(before[key], after[key])

    def test_upstream_errors_are_safe_and_loopback_only(self):
        for url in ("https://example.com", "http://0.0.0.0:8810", "http://127.0.0.1:8810/path", "http://user@127.0.0.1:8810"):
            with self.assertRaises(ValueError):
                create_observer(url, self.token, self.grant)
        for timeout in (True, False):
            def fail(request):
                if timeout:
                    raise httpx.ReadTimeout(self.token)
                return httpx.Response(500, text=self.token)
            app = create_observer("http://127.0.0.1:8999", self.token, self.grant, transport=httpx.MockTransport(fail))
            with TestClient(app, base_url="http://127.0.0.1:8810") as client:
                client.post("/observer/pair", json={"grant": self.grant}, headers=self.headers)
                response = client.get("/observer/api/fixtures", headers=self.headers)
                self.assertEqual(response.status_code, 504 if timeout else 502)
                self.assertNotIn(self.token, response.text)
