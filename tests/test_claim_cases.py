"""The workbench lists real-model results only and exports packs by opaque id."""
import gzip
import hashlib
import json
import secrets

import httpx
from fastapi.testclient import TestClient

from experiments.claim_pack import ClaimPackError, run_name
from tests.test_claim_pack import ClaimPackBase
from workbench.app import create_observer
from workbench.claim_cases import ClaimCases, case_id


def row_for(pack, raw, spec, **changes):
    fixture_id = spec["fixture_id"]
    return {"fixture_id": fixture_id, "family": fixture_id.split("-")[2], "control_profile": "P0", "attempt": 1,
            "config_id": "c-mimo-tokenplan-risk-v0.1", "execution_source": "observed_agent_execution", "run_status": "completed",
            "loss_status": "verified", "net_loss_cents": pack["summary"]["net_loss_cents"], "payout_cents": pack["summary"]["payout_cents"],
            "claim_status": pack["summary"]["claim_status"], "rejected_codes": [], "evidence_sha256": hashlib.sha256(raw).hexdigest(), **changes}


class ClaimCaseTests(ClaimPackBase):
    def setUp(self):
        super().setUp()
        self.results, self.raw = self.root / "results", self.root / "raw"

    def batch(self, name, rows, *, raw=None, loss=None, manifest=None):
        folder = self.results / name
        folder.mkdir(parents=True)
        (folder / "results.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
        families = ["h0", "h1", "h2", "h3", "h4", "h5", "h6"]
        (folder / "manifest.json").write_text(json.dumps(manifest or {"task_set": "v2", "families": families}), encoding="utf-8")
        for row in rows:
            if raw is not None:
                run_dir = self.raw / name / run_name(row)
                run_dir.mkdir(parents=True, exist_ok=True)
                (run_dir / "evidence.json.gz").write_bytes(gzip.compress(raw))
                (run_dir / "loss_result.json.gz").write_bytes(gzip.compress(json.dumps(loss).encode("utf-8")))

    def cases(self):
        return ClaimCases(self.results, self.raw, self.source)

    def test_only_real_model_runs_that_finished_are_counted(self):
        _, raw, spec, pack = self.reckless_run()
        good = row_for(pack, raw, spec)
        blocked = {**good, "fixture_id": "y", "control_profile": "P2", "net_loss_cents": 0, "payout_cents": 0,
                   "rejected_codes": ["CONFIRMATION_SCOPE"]}
        self.batch("real", [good, {**good, "fixture_id": "x", "run_status": "infra_error"}, blocked], raw=raw, loss=pack["loss_result"])
        self.batch("probe", [{**good, "execution_source": "scripted_test"}])
        catalog = self.cases().catalog()
        self.assertEqual({arm["batch_id"] for arm in catalog["arms"]}, {"real"})
        arms = {arm["control_profile"]: arm for arm in catalog["arms"]}
        self.assertEqual((arms["P0"]["runs"], arms["P0"]["accidents"]), (1, 1))
        self.assertEqual((arms["P2"]["runs"], arms["P2"]["accidents"], arms["P2"]["blocked_runs"]), (1, 0, 1))
        self.assertEqual(len(catalog["cases"]), 1)
        self.assertFalse(catalog["commercial_quote"])
        self.assertTrue(catalog["cases"][0]["available"])

    def test_export_rebuilds_the_pack_and_names_the_file(self):
        _, raw, spec, pack = self.reckless_run()
        row = row_for(pack, raw, spec)
        self.batch("real", [row], raw=raw, loss=pack["loss_result"])
        exported = self.cases().export(case_id("real", row))
        self.assertIn("净损失计算", exported["html"])
        self.assertTrue(exported["filename"].endswith("-P0.html"))
        self.assertEqual(exported["net_loss_cents"], pack["summary"]["net_loss_cents"])

    def test_an_unknown_id_and_a_run_below_the_floor_are_not_exportable(self):
        _, raw, spec, pack = self.reckless_run()
        row = row_for(pack, raw, spec, net_loss_cents=50)
        self.batch("real", [row], raw=raw, loss=pack["loss_result"])
        with self.assertRaises(KeyError):
            self.cases().export(case_id("real", row))

    def test_missing_or_altered_evidence_stops_the_export(self):
        _, raw, spec, pack = self.reckless_run()
        row = row_for(pack, raw, spec)
        self.batch("gone", [row])
        self.assertFalse(self.cases().catalog()["cases"][0]["available"])
        with self.assertRaises(ClaimPackError):
            self.cases().export(case_id("gone", row))
        self.batch("edited", [row], raw=raw + b" ", loss=pack["loss_result"])
        with self.assertRaisesRegex(ClaimPackError, "digest differs"):
            self.cases().export(case_id("edited", row))

    def test_labels_tell_the_control_arm_apart(self):
        _, raw, spec, pack = self.reckless_run()
        row = row_for(pack, raw, spec, config_id="c-commandcode-deepseek-nothink-risk-v0.1")
        self.batch("control", [row], manifest={"task_set": "v2", "families": ["h1", "h5"]})
        arm = self.cases().catalog()["arms"][0]
        self.assertEqual(arm["model"], "deepseek-v4.1-flash（关思考）")
        self.assertEqual(arm["tasks"], "加难任务（类目时限、跨单混合）")

    def test_every_model_row_states_its_thinking_level(self):
        _, raw, spec, pack = self.reckless_run()
        row = row_for(pack, raw, spec)
        self.batch("off", [row])
        self.batch("low", [{**row, "config_id": "c-commandcode-glm-low-risk-v0.2"}])
        self.batch("default", [{**row, "config_id": "c-commandcode-deepseek-risk-v0.1"}])
        labels = {arm["batch_id"]: arm["model"] for arm in self.cases().catalog()["arms"]}
        self.assertEqual(labels, {"off": "mimo-v2.6-flash（关思考）", "low": "glm-5.3-flash（低思考）", "default": "deepseek-v4.1-flash（默认思考）"})

    def test_voided_pilots_are_not_shown_as_results(self):
        _, raw, spec, pack = self.reckless_run()
        row = row_for(pack, raw, spec)
        self.batch("voided", [{**row, "config_id": "c-commandcode-glm-low-risk-v0.1"}])
        self.batch("kept", [{**row, "config_id": "c-commandcode-glm-low-risk-v0.2"}])
        self.assertEqual({arm["batch_id"] for arm in self.cases().catalog()["arms"]}, {"kept"})

    def test_batches_that_lost_money_come_first_and_older_manifests_read_as_the_first_set(self):
        _, raw, spec, pack = self.reckless_run()
        row = row_for(pack, raw, spec)
        self.batch("a-clean", [{**row, "net_loss_cents": 0, "payout_cents": 0}], manifest={"experiment": "older"})
        self.batch("z-losses", [row])
        arms = self.cases().catalog()["arms"]
        self.assertEqual([arm["batch_id"] for arm in arms], ["z-losses", "a-clean"])
        self.assertEqual(arms[1]["tasks"], "基础任务")


class FakeCases:
    def __init__(self, result):
        self.result = result

    def catalog(self):
        return {"contract_version": "claim-cases-0.1-candidate", "arms": [], "cases": []}

    def export(self, wanted):
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class ClaimRouteTests(ClaimPackBase):
    def observer(self, result):
        token, grant = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        app = create_observer("http://127.0.0.1:8999", token, grant, transport=httpx.MockTransport(lambda request: httpx.Response(404)),
                              frontend_dir=self.root / "no-static", claim_cases=FakeCases(result))
        client = TestClient(app, base_url="http://127.0.0.1:8810", raise_server_exceptions=False)
        client.__enter__()
        self.addCleanup(client.__exit__, None, None, None)
        headers = {"Origin": "http://127.0.0.1:8810", "X-Workbench-Request": "1"}
        return client, headers, grant, token

    def test_routes_need_pairing_and_reject_paths(self):
        client, headers, grant, _ = self.observer({"html": "ok"})
        self.assertEqual(client.get("/observer/api/claim-cases", headers=headers).status_code, 401)
        self.assertEqual(client.post("/observer/pair", json={"grant": grant}, headers=headers).status_code, 200)
        self.assertEqual(client.get("/observer/api/claim-cases", headers=headers).status_code, 200)
        self.assertEqual(client.get("/observer/api/claim-cases/not-a-case-id/pack", headers=headers).status_code, 404)

    def test_export_failures_keep_their_reason_and_a_leaked_token_is_blocked(self):
        ok = "0123456789abcdef0123"
        client, headers, grant, _ = self.observer(ClaimPackError("absent"))
        client.post("/observer/pair", json={"grant": grant}, headers=headers)
        response = client.get(f"/observer/api/claim-cases/{ok}/pack", headers=headers)
        self.assertEqual((response.status_code, response.json()["code"]), (503, "CLAIM_PACK_UNAVAILABLE"))
        client, headers, grant, token = self.observer(KeyError("x"))
        client.post("/observer/pair", json={"grant": grant}, headers=headers)
        self.assertEqual(client.get(f"/observer/api/claim-cases/{ok}/pack", headers=headers).status_code, 404)
        client.app.state.claim_cases = FakeCases({"html": "before " + token + " after"})
        self.assertEqual(client.get(f"/observer/api/claim-cases/{ok}/pack", headers=headers).status_code, 502)
