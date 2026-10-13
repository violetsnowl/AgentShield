"""Read-only administrator export over HTTP. JSONL is regenerated from SQLite-backed facts."""
import argparse
import json
import os
from pathlib import Path

from scripts.bc_smoke_test import HttpClient, expect


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    token = os.environ.get("AGENTSHIELD_ADMIN_TOKEN")
    if not token:
        raise SystemExit("Set AGENTSHIELD_ADMIN_TOKEN locally.")
    if not all(character.isalnum() or character in "-_.:" for character in args.session_id):
        raise SystemExit("Invalid session identifier")
    client = HttpClient(args.base_url, token)
    evidence = expect(client.request("GET", f"/api/v1/admin/sessions/{args.session_id}/evidence"))
    destination = Path(args.output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "evidence.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (destination / "events.jsonl").write_text("".join(json.dumps(event, ensure_ascii=False) + "\n" for event in evidence["events"]), encoding="utf-8")
    print("Read-only evidence and recoverable JSONL export saved.")


if __name__ == "__main__":
    main()
