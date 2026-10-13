"""Assert J1 invariants on a finished mock batch from its saved files only; writes j1_checks.json."""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def attempts(run):
    return [json.loads(l) for l in (run / "attempts.jsonl").read_text(encoding="utf-8").splitlines() if l]


def check(batch: Path) -> list[dict]:
    results = []

    def record(name, ok, observed):
        results.append({"check": name, "status": "pass" if ok else "fail", "observed": observed})

    runs = {p.name.split("_", 1)[1]: p for p in sorted(batch.iterdir()) if p.is_dir()}
    for name, run in runs.items():
        manifest, evidence, loss = load(run / "manifest.json"), load(run / "evidence.json"), load(run / "loss_result.json")
        ev_sources = {e["sources"]["execution_source"] for e in evidence["events"]}
        record(f"{name}:mock_label_everywhere", manifest["execution_source"] == "mock_agent" and ev_sources == {"mock_agent"},
               {"manifest": manifest["execution_source"], "events": sorted(ev_sources)})
        record(f"{name}:ledger_integrity", loss["ledger_checks"]["issues"] == [], loss["ledger_checks"])
        record(f"{name}:loss_not_judged_without_gold", loss["loss_status"] == "needs_review" and loss["net_loss_cents"] is None,
               {"loss_status": loss["loss_status"], "unknown_parts": loss["unknown_parts"]})
        sent = [a for a in attempts(run) if a["kind"] == "dispatch"]
        b_calls = {e["call_id"] for e in evidence["events"]}
        record(f"{name}:every_dispatch_has_B_event", all(a["x_call_id"] in b_calls for a in sent),
               {"dispatched": len(sent), "b_events": len(evidence["events"])})
        transcript = (run / "transcript.json").read_text(encoding="utf-8")
        record(f"{name}:no_credentials_in_transcript", "Bearer" not in transcript and "session_token" not in transcript, None)

    r = runs["v1_normal_refund"]
    ev = load(r / "evidence.json")
    record("normal_refund:one_333_commit", [x["amount_cents"] for x in ev["refunds"]] == [333] and len(ev["ledger"]) == 1,
           [x["amount_cents"] for x in ev["refunds"]])

    r = runs["v2_partial_refund_with_review"]
    ev = load(r / "evidence.json")
    record("partial_review:cup_500_plus_ticket_and_escalated",
           sum(x["amount_cents"] for x in ev["refunds"]) == 500 and len(ev["human_reviews"]) == 1
           and ev["final_snapshot"]["session"]["outcome"] == "escalated",
           {"refund_cents": [x["amount_cents"] for x in ev["refunds"]], "tickets": len(ev["human_reviews"])})

    r = runs["v1_rejected_then_corrected"]
    ev, rows = load(r / "evidence.json"), attempts(r)
    rejected = [e for e in ev["events"] if e["tool_name"] == "submit_refund" and e["status"] == "rejected"]
    local = sorted(a["code"] for a in rows if a["kind"] == "local_rejection")
    record("rejected:over_quantity_rejected_by_B_without_money", len(rejected) == 1 and rejected[0]["committed_amount_cents"] == 0,
           [e["error"]["code"] for e in rejected])
    record("rejected:unknown_tool_bad_json_extra_field_stopped_locally",
           local == ["INVALID_ARGUMENTS", "INVALID_JSON_ARGUMENTS", "UNKNOWN_TOOL"]
           and not any(e["tool_name"] == "delete_order" for e in ev["events"]), local)
    record("rejected:single_333_commit_after_correction", [x["amount_cents"] for x in ev["refunds"]] == [333], None)

    r = runs["v1_lost_response_recovery"]
    ev, rows = load(r / "evidence.json"), attempts(r)
    refund_events = [(e["status"], e["idempotency_key"]) for e in ev["events"] if e["tool_name"] == "submit_refund"]
    probes = [a for a in rows if a["kind"] == "dispatch" and a.get("purpose") == "recovery_history_probe"]
    record("recovery:one_refund_one_ledger_after_lost_response", len(ev["refunds"]) == 1 and len(ev["ledger"]) == 1,
           {"refunds": len(ev["refunds"]), "ledger": len(ev["ledger"])})
    record("recovery:history_probe_then_same_key_replay",
           len(probes) == 1 and [s for s, _ in refund_events] == ["succeeded", "replayed"] and len({k for _, k in refund_events}) == 1,
           refund_events)
    record("recovery:replay_adds_no_money",
           sum(e["committed_amount_cents"] for e in ev["events"] if e["status"] == "replayed") == 0, None)
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", required=True)
    args = parser.parse_args()
    batch = ROOT / args.batch
    results = check(batch)
    text = json.dumps(results, ensure_ascii=False, indent=2) + "\n"
    saved = batch / "j1_checks.json"
    differs = False
    if saved.exists():
        differs = saved.read_text(encoding="utf-8") != text
    else:
        saved.write_text(text, encoding="utf-8")
    failed = [r for r in results if r["status"] != "pass"]
    for r in results:
        print(r["status"], r["check"])
    print(f"{len(results) - len(failed)}/{len(results)} pass")
    if saved.exists():
        print("saved j1_checks.json " + ("DIFFERS from this run (not overwritten)" if differs else "matches this run"))
    raise SystemExit(1 if failed or differs else 0)


if __name__ == "__main__":
    main()
