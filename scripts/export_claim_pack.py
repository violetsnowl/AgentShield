"""Export Chinese claim packs for a risk batch, or check one that was exported.

  python -m scripts.export_claim_pack --batch risk-hard-mimo-20261105-203613 --limit 3
  python -m scripts.export_claim_pack --batch <batch> --run P0_risk-v2-h5-rr-synth-00006884_a1
  python -m scripts.export_claim_pack --verify var/claim_packs/<batch>/<run>

Packs go to var/ (Git-ignored). Without --run, a batch exports its largest accidents first.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from experiments.claim_pack import ROOT, ClaimPackError, is_accident, latest_rows, pack_for_row, run_name, verify_pack, write_pack
from experiments.run_matrix import resolve_source


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch")
    parser.add_argument("--run", help="Run folder name; default is every accident of the batch")
    parser.add_argument("--limit", type=int, help="Largest accidents only")
    parser.add_argument("--out", type=Path, help="Default var/claim_packs/<batch>")
    parser.add_argument("--source-db")
    parser.add_argument("--verify", type=Path, help="Check an exported pack instead of exporting")
    args = parser.parse_args(argv)
    if args.verify:
        problems = verify_pack(args.verify)
        print(json.dumps({"pack": str(args.verify), "ok": not problems, "problems": problems}, ensure_ascii=False))
        return 1 if problems else 0
    if not args.batch:
        parser.error("--batch or --verify is required")
    rows = latest_rows(args.batch)
    if args.run:
        rows = [row for row in rows if run_name(row) == args.run]
        if not rows:
            raise SystemExit(f"No run named {args.run} in {args.batch}")
    else:
        rows = sorted((row for row in rows if is_accident(row)), key=lambda row: -row["net_loss_cents"])
        rows = rows[:args.limit] if args.limit else rows
    source = resolve_source(args.source_db)
    out_root = args.out or ROOT / "var/claim_packs" / args.batch
    failed = 0
    for row in rows:
        try:
            pack, raw = pack_for_row(args.batch, row, source)
        except ClaimPackError as error:
            failed += 1
            print(json.dumps({"run": run_name(row), "error": str(error)}, ensure_ascii=False))
            continue
        target = out_root / run_name(row)
        write_pack(pack, raw, target)
        print(json.dumps({"run": run_name(row), "net_loss_cents": pack["summary"]["net_loss_cents"],
                          "payout_cents": pack["summary"]["payout_cents"], "claim_status": pack["summary"]["claim_status"],
                          "out": str(target)}, ensure_ascii=False))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
