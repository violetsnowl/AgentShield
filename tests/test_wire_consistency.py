import ast
import hashlib
import json
from pathlib import Path
import unittest

import jsonschema

from api.app import create_app
from contracts import models as m
from scripts.export_contracts import products


class WireConsistencyTests(unittest.TestCase):
    def test_openapi_matches_actual_routes_and_shared_models(self):
        api = create_app(None, None, initialize=False).openapi()
        self.assertEqual(json.loads(Path("contracts/openapi.json").read_text(encoding="utf-8")), api)
        tool_paths = [p for p in api["paths"] if "/tools/" in p]
        self.assertEqual(len(tool_paths), len(m.TOOLS))
        self.assertEqual(len(m.TOOLS), 7)
        for name, (request, response, write, _) in m.TOOLS.items():
            operation = api["paths"][f"/api/v1/sessions/{{session_id}}/tools/{name}"]["post"]
            self.assertEqual(operation["requestBody"]["content"]["application/json"]["schema"]["$ref"], f"#/components/schemas/{request.__name__}")
            self.assertEqual(operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"], f"#/components/schemas/{response.__name__}")
            key_header = next(parameter for parameter in operation["parameters"] if parameter["name"] == "Idempotency-Key")
            self.assertEqual(key_header["required"], write)
            self.assertEqual(operation["responses"]["422"]["content"]["application/json"]["schema"]["$ref"], "#/components/schemas/Error")
            self.assertEqual(operation["security"], [{"HTTPBearer": []}])
        self.assertFalse(any("quotes" in path or "evaluate" in path for path in api["paths"]))

    def test_captured_http_responses_and_fixed_examples_validate(self):
        for path in (Path("contracts/response_examples.json"), Path("artifacts/b_bootstrap/http_smoke/http_responses.json")):
            examples = json.loads(path.read_text(encoding="utf-8"))
            expected = set(m.TOOLS) if path.parent.name == "contracts" else set(m.TOOLS) - {"submit_human_review"}
            self.assertEqual(set(examples), expected)  # Keep the original six-tool capture immutable and readable.
            for name, body in examples.items():
                response_model = m.TOOLS[name][1]
                response_model.model_validate(body)
                jsonschema.validate(body, response_model.model_json_schema())

    def test_evidence_and_jsonl_match_authoritative_schema(self):
        directory = Path("artifacts/b_bootstrap/http_smoke")
        evidence = json.loads((directory / "evidence_sample.json").read_text(encoding="utf-8"))
        m.EvidenceBundle.model_validate(evidence)
        jsonschema.validate(evidence, m.EvidenceBundle.model_json_schema())
        events = [json.loads(line) for line in (directory / "events_sample.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual(evidence["events"], events)
        self.assertEqual(evidence["refunds"][0]["amount_cents"], 333)
        self.assertEqual(evidence["ledger"][0]["merchant_delta_cents"], -333)
        self.assertEqual(evidence["initial_snapshot"]["merchant_balance_cents"], 1700)
        self.assertEqual(evidence["final_snapshot"]["merchant_balance_cents"], 1367)

    def test_current_evidence_and_event_examples_include_ticket_without_money(self):
        evidence = json.loads(Path("contracts/evidence_example.json").read_text(encoding="utf-8"))
        m.EvidenceBundle.model_validate(evidence)
        jsonschema.validate(evidence, m.EvidenceBundle.model_json_schema())
        self.assertEqual(evidence["schema_version"], 3)
        self.assertEqual(evidence["case_context_status"], "recorded")
        self.assertEqual(len(evidence["human_reviews"]), 1)
        self.assertEqual(evidence["human_reviews"][0]["status"], "open")
        self.assertEqual(len(evidence["refunds"]), 1)
        self.assertEqual(evidence["refunds"][0]["amount_cents"], 333)
        events = json.loads(Path("contracts/tool_event_examples.json").read_text(encoding="utf-8"))
        for event in events:
            m.ToolEvent.model_validate(event)
            jsonschema.validate(event, m.ToolEvent.model_json_schema())
        self.assertEqual({e["status"] for e in events}, {"rejected", "succeeded", "replayed"})
        self.assertTrue(all(e["committed_amount_cents"] == 0 for e in events))

    def test_execution_source_examples_match_both_schema_and_model(self):
        examples = json.loads(Path("contracts/session_source_examples.json").read_text(encoding="utf-8"))
        self.assertEqual(examples["model_calls"], 0)
        self.assertFalse(examples["real_execution_proof"])
        self.assertEqual({example["execution_source"] for example in examples["requests"]},
                         {"scripted_test", "mock_agent", "observed_agent_execution"})
        for example in examples["requests"]:
            m.CreateSession.model_validate(example)
            jsonschema.validate(example, m.CreateSession.model_json_schema())

    def test_smoke_script_imports_standard_library_only(self):
        # Protect the B/C boundary; this artifact must run outside the repository with stock Python.
        allowed = {"argparse", "copy", "hashlib", "json", "os", "pathlib", "urllib", "uuid"}
        tree = ast.parse(Path("scripts/bc_smoke_test.py").read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                self.assertTrue(all(alias.name.split(".")[0] in allowed for alias in node.names))
            if isinstance(node, ast.ImportFrom):
                self.assertIn(node.module.split(".")[0], allowed)

    def test_case_examples_show_pairing_and_verify_public_hashes(self):
        examples = json.loads(Path("contracts/case_examples.json").read_text(encoding="utf-8"))
        for request in examples["create_requests"]:
            m.CreateSession.model_validate(request)
            jsonschema.validate(request, m.CreateSession.model_json_schema())
        for context in examples["contexts"]:
            m.CaseContext.model_validate(context)
            jsonschema.validate(context, m.CaseContext.model_json_schema())
            encoded = json.dumps(context["canonical_initial"], ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
            self.assertEqual(hashlib.sha256(encoded).hexdigest(), context["business_initial_hash"])
        first, second, v2 = examples["contexts"]
        self.assertEqual(first["case_id"], second["case_id"])
        self.assertEqual(first["business_initial_hash"], second["business_initial_hash"])
        self.assertNotEqual(first["object_mapping"], second["object_mapping"])
        self.assertNotEqual(first["case_id"], v2["case_id"])
        evidence = json.loads(Path("contracts/fixture_v2_evidence_example.json").read_text(encoding="utf-8"))
        jsonschema.validate(evidence, m.EvidenceBundle.model_json_schema())
        self.assertEqual(evidence["case_context"], v2)
        self.assertEqual(evidence["refunds"][0]["amount_cents"], 250)
        self.assertEqual(len(evidence["human_reviews"]), 1)

    def test_registered_fixture_files_match_exported_schema(self):
        registry = json.loads(Path("contracts/fixture_registry.json").read_text(encoding="utf-8"))
        schema = json.loads(Path("contracts/development_fixture.schema.json").read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator.check_schema(schema)
        from sandbox.fixture import REGISTRY, load_fixture
        self.assertEqual([entry["fixture_id"] for entry in registry["fixtures"]], list(REGISTRY))
        for entry in registry["fixtures"]:
            fixture, content_hash = load_fixture(entry["fixture_id"])
            jsonschema.validate(fixture, schema)
            self.assertEqual(content_hash, entry["fixture_content_sha256"])


if __name__ == "__main__":
    unittest.main()
