"""Obligation specs are authored and reviewed by A/D (Gold custody). The runner never reads them."""
import json
from pathlib import Path
from typing import Any

SPEC_VERSION = "obligation-spec-0.1-candidate"
REQUIRED = ("spec_version", "spec_id", "case_id", "fixture_id", "fixture_version", "policy_version", "source",
            "review_status", "closed_world", "obligations", "recovery", "coverage_status_input", "allowed_outcomes", "horizon")


class SpecError(ValueError):
    pass


def load_spec(path: Path) -> dict[str, Any]:
    spec = json.loads(path.read_text(encoding="utf-8"))
    validate_spec(spec)
    return spec


def validate_spec(spec: dict[str, Any]) -> None:
    missing = [key for key in REQUIRED if key not in spec]
    if missing:
        raise SpecError("obligation spec missing: " + ", ".join(missing))
    if spec["spec_version"] != SPEC_VERSION:
        raise SpecError("unsupported obligation spec version")
    if spec["coverage_status_input"] not in ("covered", "excluded", "needs_review"):
        raise SpecError("coverage_status_input must be covered/excluded/needs_review")
    refs = set()
    for item in spec["obligations"]:
        for key in ("ref", "template_order_id", "template_item_id", "legally_due_cents"):
            if key not in item:
                raise SpecError(f"obligation missing {key}")
        due = item["legally_due_cents"]
        if due is not None and (type(due) is not int or due < 0):
            raise SpecError("legally_due_cents must be a non-negative integer or null")
        if item["ref"] in refs:
            raise SpecError("duplicate obligation ref")
        refs.add(item["ref"])
    recovery = spec["recovery"]
    if recovery.get("policy") not in ("none_in_sandbox", "explicit"):
        raise SpecError("recovery.policy must be none_in_sandbox or explicit")


def check_matches(spec: dict[str, Any], identity: dict[str, Any]) -> None:
    for key in ("case_id", "fixture_id", "fixture_version", "policy_version"):
        if spec[key] != identity.get(key):
            raise SpecError(f"obligation spec {key} does not match the evidence")
