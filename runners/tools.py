"""Model-facing tool whitelist derived from B's exported contracts; strict local validation before dispatch."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from contracts import models as wire

ROOT = Path(__file__).resolve().parents[1]
TOOLS_FILE = ROOT / "contracts/tools.json"
WRITE_TOOLS = frozenset(name for name, spec in wire.TOOLS.items() if spec[2])
# Transport-level recovery key is owned by the runner, never chosen by the model.
RUNNER_ONLY_FIELDS = {"get_refund_history": {"idempotency_key"}}
VERSION_HINTS = {
    "submit_refund": "expected_version is the current ORDER version from get_order.",
    "submit_human_review": "expected_version is the current SESSION version (from the latest write result or get_case flow).",
    "finish_case": "expected_version is the current SESSION version.",
}


def _inline_refs(schema: dict[str, Any]) -> dict[str, Any]:
    defs = schema.pop("$defs", {})

    def walk(node):
        if isinstance(node, dict):
            if "$ref" in node:
                return walk(deepcopy(defs[node["$ref"].rsplit("/", 1)[-1]]))
            return {k: walk(v) for k, v in node.items()}
        if isinstance(node, list):
            return [walk(v) for v in node]
        return node
    return walk(schema)


def model_tool_specs() -> list[dict[str, Any]]:
    specs = json.loads(TOOLS_FILE.read_text(encoding="utf-8"))
    names = [spec["function"]["name"] for spec in specs]
    if sorted(names) != sorted(wire.TOOLS):
        raise RuntimeError("contracts/tools.json does not match the B tool registry")
    out = []
    for spec in specs:
        function = deepcopy(spec["function"])
        params = _inline_refs(function["parameters"])
        for field in RUNNER_ONLY_FIELDS.get(function["name"], ()):
            params.get("properties", {}).pop(field, None)
            if field in params.get("required", []):
                params["required"].remove(field)
        params.pop("title", None)
        function["parameters"] = params
        if function["name"] in VERSION_HINTS:
            function["description"] += " " + VERSION_HINTS[function["name"]]
        out.append({"type": "function", "function": function})
    return out


def tool_specs_sha256(specs: list[dict[str, Any]]) -> str:
    return hashlib.sha256(json.dumps(specs, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


class LocalRejection(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message

    def payload(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "retryable": False, "source": "runner_local_validation"}


def validate_call(name: str, arguments_text: str) -> dict[str, Any]:
    """Return validated arguments or raise LocalRejection. Never evaluates model text."""
    if name not in wire.TOOLS:
        raise LocalRejection("UNKNOWN_TOOL", "Tool is not in the public whitelist.")
    try:
        raw = json.loads(arguments_text or "{}")
    except ValueError:
        raise LocalRejection("INVALID_JSON_ARGUMENTS", "Tool arguments must be one JSON object.") from None
    if not isinstance(raw, dict):
        raise LocalRejection("INVALID_JSON_ARGUMENTS", "Tool arguments must be one JSON object.")
    forbidden = RUNNER_ONLY_FIELDS.get(name, set()) & set(raw)
    if forbidden:
        raise LocalRejection("INVALID_ARGUMENTS", "Field not permitted for this tool: " + ", ".join(sorted(forbidden)))
    try:
        model = wire.TOOLS[name][0].model_validate(raw)
    except ValidationError as error:
        fields = sorted({".".join(str(p) for p in issue["loc"]) or "(root)" for issue in error.errors()})
        raise LocalRejection("INVALID_ARGUMENTS", "Invalid or unexpected fields: " + ", ".join(fields)[:500]) from None
    return model.model_dump(exclude_none=True) if name == "get_refund_history" else model.model_dump()
