"""Run with python -m scripts.export_contracts [--check] [--with-openapi]."""
import argparse
import json
from pathlib import Path

from contracts import models as m
from sandbox.fixture import REGISTRY, business_hash, canonical_snapshot, load_fixture
from sandbox.fixture_models import DevelopmentFixture

ROOT = Path(__file__).resolve().parents[1]


def products(with_openapi=False):
    schemas = {name: obj.model_json_schema() for name, obj in vars(m).items()
               if isinstance(obj, type) and issubclass(obj, m.Wire) and obj is not m.Wire}
    tools = [{"type": "function", "function": {"name": name, "description": description,
              "parameters": req.model_json_schema()}}
             for name, (req, _, _, description) in m.TOOLS.items()]
    status = {"version": m.VERSION, "review_status": "candidate_pending_A_C_D_review",
              "implemented": list(m.TOOLS), "planned": list(m.PLANNED_TOOLS),
              "enable_paid_runs": False, "max_cost": 0}
    result = {"schemas.json": schemas, "tools.json": tools, "implementation_status.json": status}
    result["development_fixture.schema.json"] = DevelopmentFixture.model_json_schema()
    registry = []
    for fixture_id in REGISTRY:
        fixture, content_hash = load_fixture(fixture_id)
        registry.append({key: fixture[key] for key in ("fixture_id", "fixture_version", "source_case_id", "parent_case_id", "family_id", "fixture_source", "review_status")} | {
            "fixture_content_sha256": content_hash, "policy_version": fixture["policy"]["policy_version"],
            "environment_version": m.ENVIRONMENT_VERSION,
            "business_initial_hash": business_hash(canonical_snapshot(fixture))})
    result["fixture_registry.json"] = {"version": m.VERSION, "registration": "source_controlled_development_only", "fixtures": registry}
    if with_openapi:
        from api.app import create_app
        result["openapi.json"] = create_app(None, None, initialize=False).openapi()
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--with-openapi", action="store_true")
    args = parser.parse_args()
    for name, content in products(args.with_openapi).items():
        path = ROOT / "contracts" / name
        rendered = json.dumps(content, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        if args.check:
            if not path.exists() or path.read_text(encoding="utf-8") != rendered:
                raise SystemExit(f"Contract drift: {name}")
        else:
            path.write_text(rendered, encoding="utf-8")
    print("Contract artifacts match source models." if args.check else "Exported candidate contracts.")


if __name__ == "__main__":
    main()
