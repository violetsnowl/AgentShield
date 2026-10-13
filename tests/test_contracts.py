import json
from pathlib import Path
import unittest

import jsonschema
from pydantic import ValidationError

from contracts import models as m
from scripts.export_contracts import products


class ContractTests(unittest.TestCase):
    def test_fixed_requests_match_schema_and_server_models(self):
        examples = json.loads(Path("contracts/examples.json").read_text(encoding="utf-8"))
        self.assertEqual(set(examples["requests"]), set(m.TOOLS))
        for name, (req, _, _, _) in m.TOOLS.items():
            example = examples["requests"][name]
            req.model_validate(example)
            jsonschema.validate(example, req.model_json_schema())
        jsonschema.validate(examples["error"], m.Error.model_json_schema())

    def test_amount_extra_fields_and_non_integer_quantities_rejected(self):
        valid = json.loads(Path("contracts/examples.json").read_text())["requests"]["submit_refund"]
        for quantity in (0, -1, True, 1.0, "1"):
            invalid = {**valid, "items": [{"item_id": "i", "quantity": quantity}]}
            with self.assertRaises(ValidationError):
                m.RefundRequest.model_validate(invalid)
        for extra in ({"amount_cents": 999}, {"tenant_id": "other"}, {"channel": "other"}):
            with self.assertRaises(ValidationError):
                m.RefundRequest.model_validate({**valid, **extra})

    def test_generated_schemas_tools_and_status_match(self):
        for name, content in products().items():
            self.assertEqual(json.loads((Path("contracts") / name).read_text(encoding="utf-8")), content)
        self.assertIn("submit_human_review", m.TOOLS)
        self.assertNotIn("submit_human_review", m.PLANNED_TOOLS)
        for schema in products()["schemas.json"].values():
            jsonschema.Draft202012Validator.check_schema(schema)


if __name__ == "__main__":
    unittest.main()
