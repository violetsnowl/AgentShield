"""Idempotent schema initialization; never resets or removes existing data."""
import argparse
from pathlib import Path

from sandbox.store import Store


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="var/development.sqlite3")
    args = parser.parse_args()
    path = Path(args.db).resolve()
    root = Path(__file__).resolve().parents[1]
    if not path.is_relative_to(root / "var"):
        raise SystemExit("Development initialization is restricted to this project's var/ directory.")
    Store(path).initialize()
    print("Development schema initialized (existing sessions preserved).")


if __name__ == "__main__":
    main()
