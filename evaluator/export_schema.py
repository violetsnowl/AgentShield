"""Export the LossResult candidate JSON Schema; --check fails on drift instead of overwriting."""
import argparse
import json
from pathlib import Path

from .models import LossResult

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "contracts/loss_result_C_v0.1_candidate.schema.json"


def render() -> str:
    schema = LossResult.model_json_schema()
    schema["$comment"] = "C candidate, pending A/D review. Integer cents; null means unknown, never zero."
    return json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    text = render()
    if args.check:
        if not TARGET.exists() or TARGET.read_text(encoding="utf-8") != text:
            raise SystemExit("LossResult schema drift: contracts/loss_result_C_v0.1_candidate.schema.json")
        print("LossResult schema matches evaluator/models.py")
        return
    TARGET.write_text(text, encoding="utf-8")
    print("wrote " + TARGET.relative_to(ROOT).as_posix())


if __name__ == "__main__":
    main()
