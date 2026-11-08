"""A tamper-evident chain over every recorded run.

  python -m experiments.evidence_chain            write artifacts/risk_runs/evidence_chain.json
  python -m experiments.evidence_chain --verify   check it against the batches, and raw evidence where present

Each link hashes the previous link and one whole result row, so changing,
dropping or reordering any record changes the root. The root goes into the public Git history, which gives
it a date nobody here controls. This shows the records were not altered afterwards. It cannot show they were
true when written; that takes an independent source such as a payment-channel statement.
"""
from __future__ import annotations

import argparse
import gzip
from hashlib import sha256
import json
from pathlib import Path
import sys
from typing import Any, Iterable

from experiments.claim_pack import RAW_ROOT, RESULTS_ROOT, ROOT, run_name

CHAIN_FILE = RESULTS_ROOT / "evidence_chain.json"
SCHEMA = "AgentShield.evidence_chain.v0.1"
GENESIS = "0" * 64


def link(previous: str, batch: str, row: dict[str, Any]) -> str:
    body = json.dumps({"batch": batch, "row": row}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(f"{previous}:{body}".encode("utf-8")).hexdigest()


def batch_rows(folder: Path) -> Iterable[dict[str, Any]]:
    for line in (folder / "results.jsonl").read_text(encoding="utf-8").splitlines():
        if line:
            yield json.loads(line)


def build(results_root: Path = RESULTS_ROOT) -> dict[str, Any]:
    tip, batches, links = GENESIS, [], 0
    for folder in sorted(path for path in results_root.iterdir() if (path / "results.jsonl").is_file()):
        rows = 0
        for row in batch_rows(folder):
            tip = link(tip, folder.name, row)
            rows += 1
        links += rows
        batches.append({"batch": folder.name, "rows": rows, "tip": tip})
    return {"schema": SCHEMA, "links": links, "root": tip, "batches": batches}


def verify(stored: dict[str, Any], results_root: Path = RESULTS_ROOT) -> list[str]:
    """Names the first batch that no longer matches; anything after it would differ anyway."""
    current = build(results_root)
    if stored.get("schema") != SCHEMA:
        return ["unknown chain file"]
    if current["root"] == stored.get("root") and current["links"] == stored.get("links"):
        return []
    theirs = {row["batch"]: row for row in stored.get("batches", [])}
    for row in current["batches"]:
        if theirs.get(row["batch"]) != row:
            return [f"batch differs from the recorded chain: {row['batch']}"]
    return ["a recorded batch is missing"]


def verify_raw(results_root: Path = RESULTS_ROOT, raw_root: Path = RAW_ROOT) -> dict[str, Any]:
    """Raw evidence stays on this machine; where it exists, its digest must match the row that cites it."""
    checked, absent, wrong = 0, 0, []
    for folder in sorted(path for path in results_root.iterdir() if (path / "results.jsonl").is_file()):
        for row in batch_rows(folder):
            digest = row.get("evidence_sha256")
            if not digest:
                continue
            path = raw_root / folder.name / run_name(row) / "evidence.json.gz"
            if not path.is_file():
                absent += 1
                continue
            checked += 1
            if sha256(gzip.decompress(path.read_bytes())).hexdigest() != digest:
                wrong.append(f"{folder.name}/{run_name(row)}")
    return {"checked": checked, "absent": absent, "wrong": wrong}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.verify:
        problems = verify(json.loads(CHAIN_FILE.read_text(encoding="utf-8")))
        raw = verify_raw()
        print(json.dumps({"chain_problems": problems, "raw": {**raw, "wrong": raw["wrong"][:5]}}, ensure_ascii=False))
        sys.exit(1 if problems or raw["wrong"] else 0)
    chain = build()
    CHAIN_FILE.write_text(json.dumps(chain, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(CHAIN_FILE.relative_to(ROOT), chain["links"], chain["root"])
