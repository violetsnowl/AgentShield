"""Generate or verify the fixed public B candidate library."""
import argparse
from pathlib import Path

from sandbox.case_generator import check_library, load_config, write_library

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "configs/case_generator/b-cp2-v1.json"
GENERATED = ROOT / "sandbox/fixtures/generated"
MANIFEST = ROOT / "artifacts/b_case_generator/CASE_MANIFEST.json"


def main():
    parser = argparse.ArgumentParser()
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    args = parser.parse_args()
    config = load_config(Path(args.config))
    if args.write:
        write_library(config, GENERATED, MANIFEST)
        print("Generated fixed B candidate library: 40 fixtures (L0 8+4, L1 24+4).")
    else:
        check_library(config, GENERATED, MANIFEST)
        print("B candidate library matches config, seed, registry and manifest.")


if __name__ == "__main__":
    main()
