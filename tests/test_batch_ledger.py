from hashlib import sha256
import json
import re
import unittest

from experiments import batch_ledger
from experiments.claim_pack import RESULTS_ROOT, ROOT

EVIDENCE = json.loads((ROOT / "configs/insurance/annual_evidence_v0.2.json").read_text(encoding="utf-8"))
CHAIN = json.loads((RESULTS_ROOT / "evidence_chain.json").read_text(encoding="utf-8"))
SAMPLE = ROOT / "docs/validation/evidence_sample_00067996"
# Independent of batch_ledger's own patterns, so a weak pattern there cannot hide a leak here.
LEAK_SHAPES = (r"\bsk-[A-Za-z0-9_\-]{12,}", r"(?i)\bbearer\s+[A-Za-z0-9._\-]{8,}", r"(?i)authorization\s*[:=]\s*\S",
               r"(?i)(api[_-]?key|secret|password|access[_-]?token)\"?\s*[:=]\s*\"?[A-Za-z0-9._\-]{8,}", r"://[^/\s:@\"]+:[^/\s@\"]+@")


class BatchLedgerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ledger = batch_ledger.build()

    def test_totals_match_the_annual_evidence_file(self):
        totals, severity = self.ledger["totals"], EVIDENCE["severity"]
        self.assertEqual(totals["real_runs"], EVIDENCE["real_runs"])
        self.assertEqual(totals["accidents"], severity["accidents"])
        self.assertEqual(totals["net_loss_cents"], severity["net_loss_cents"])
        self.assertEqual(totals["distinct_tasks"], severity["distinct_tasks"])
        self.assertTrue(all(self.ledger["totals"]["reconciles"].values()), self.ledger["totals"]["reconciles"])

    def test_the_batch_table_adds_up_to_the_totals(self):
        counted = [line for line in self.ledger["batches"] if line["counted_in_real_runs"]]
        self.assertEqual(sum(sum(cell["runs"] for cell in line["profiles"].values()) for line in counted), EVIDENCE["real_runs"])
        self.assertEqual(sum(line["accidents"] for line in counted), EVIDENCE["severity"]["accidents"])
        self.assertEqual(sum(line["net_loss_cents"] for line in counted), EVIDENCE["severity"]["net_loss_cents"])
        for line in self.ledger["batches"]:
            self.assertEqual(sum(cell["accidents"] for cell in line["profiles"].values()), line["accidents"])
            self.assertEqual(line["raw_rows"] - line["superseded_rows"], line["latest_rows"])
            self.assertEqual(sum(line["run_status_latest"].values()), line["latest_rows"])
            self.assertEqual(line["counted_in_real_runs"], not line["voided"] and line["execution_source_latest"].get("observed_agent_execution", 0) > 0)

    def test_voided_and_scripted_batches_stay_out_of_real_runs(self):
        for line in self.ledger["batches"]:
            if line["voided"] or line["channel"].startswith("脚本"):
                self.assertFalse(line["counted_in_real_runs"], line["batch_id"])

    def test_chain_count_matches_the_chain_file(self):
        chain = self.ledger["chain"]
        self.assertEqual(chain["links_current"], CHAIN["links"])
        self.assertEqual(chain["links_stored"], CHAIN["links"])
        self.assertEqual(chain["root_current"], CHAIN["root"])
        self.assertEqual(chain["links"], CHAIN["links"])
        self.assertEqual(sum(part["links"] for part in chain["parts"].values()), CHAIN["links"])
        self.assertEqual({line["batch_id"]: line["raw_rows"] for line in self.ledger["batches"]}, {row["batch"]: row["rows"] for row in CHAIN["batches"]})

    def test_raw_evidence_parts_add_up(self):
        chain, raw = self.ledger["chain"], self.ledger["raw_evidence"]
        self.assertEqual(raw["rows_with_digest"], sum(part["with_evidence_digest"] for part in chain["parts"].values()))
        self.assertEqual(chain["parts"]["not_started"]["with_evidence_digest"], 0)
        self.assertEqual(chain["parts"]["completed_observed_counted"]["links"], EVIDENCE["real_runs"])
        self.assertEqual(raw["files_checked"] + raw["files_absent"], raw["rows_with_digest"])
        self.assertEqual(raw["files_wrong"], 0)

    def test_dedup_rules_reproduce_the_official_mean(self):
        dedup = self.ledger["dedup"]
        self.assertEqual(dedup["accident_rows"], EVIDENCE["severity"]["accidents"])
        self.assertEqual(dedup["distinct_tasks"], EVIDENCE["severity"]["distinct_tasks"])
        self.assertEqual(dedup["official_mean_of_task_means_cents"], EVIDENCE["severity"]["mean_cents"])
        self.assertEqual(sum(dedup["accident_rows_by_batch"].values()), dedup["accident_rows"])
        self.assertEqual(sum(int(times) * tasks for times, tasks in dedup["accidents_per_task"].items()), dedup["accident_rows"])
        self.assertLessEqual(dedup["official_mean_of_task_means_cents"], dedup["alt_max_mean_cents"])

    def test_the_two_mimo_batches_are_different_batches(self):
        pair = self.ledger["sentinel_pair"]
        self.assertNotEqual(pair["wide_batch"], pair["narrow_batch"])
        self.assertEqual((pair["wide_all_tasks_P0"]["runs"], pair["wide_all_tasks_P0"]["accidents"]), (210, 0))
        self.assertEqual((pair["narrow_P0"]["runs"], pair["narrow_P0"]["accidents"]), (60, 1))
        self.assertEqual({pair["wide_channel"], pair["narrow_channel"]}, {"Command Code", "官方接口"})
        self.assertTrue(pair["narrow_tasks_inside_wide"])

    def test_written_files_carry_the_same_totals(self):
        written = json.loads(batch_ledger.JSON_OUT.read_text(encoding="utf-8"))
        self.assertEqual(written["totals"]["real_runs"], EVIDENCE["real_runs"])
        self.assertEqual(written["chain"]["links_current"], CHAIN["links"])
        text = batch_ledger.MD_OUT.read_text(encoding="utf-8")
        for needle in ("4,326", "8,601,926", "9,186", "5,732", "risk-same-mimo-20261106-104537", "risk-direct-low-20261106-221729"):
            self.assertIn(needle, text)

    def test_new_files_use_lf(self):
        for path in (batch_ledger.JSON_OUT, batch_ledger.MD_OUT, *SAMPLE.glob("*")):
            self.assertNotIn(b"\r", path.read_bytes(), path.name)


class SampleTests(unittest.TestCase):
    def test_sample_has_no_key_or_token_shapes(self):
        files = [path for path in SAMPLE.iterdir() if path.is_file()]
        self.assertTrue(files)
        for path in files:
            text = path.read_text(encoding="utf-8")
            for shape in LEAK_SHAPES:
                self.assertIsNone(re.search(shape, text), f"{path.name}: matches a credential shape")
            self.assertEqual(batch_ledger.scan_file(path) if path.suffix in {".json", ".html"} else batch_ledger.scan_text(text), [], path.name)

    def test_sample_evidence_is_the_one_the_chain_records(self):
        digest = sha256((SAMPLE / "evidence.json").read_bytes()).hexdigest()
        rows = [json.loads(line) for line in (RESULTS_ROOT / batch_ledger.SAMPLE_BATCH / "results.jsonl").read_text(encoding="utf-8").splitlines() if line]
        self.assertIn(digest, {row.get("evidence_sha256") for row in rows})

    def test_sample_has_the_pieces_a_reviewer_needs(self):
        for name in ("README.md", "tool_calls.json", "final_reply.json", "ledger_before_after.json", "verification.json", "claim_pack.json", "理赔材料.html"):
            self.assertTrue((SAMPLE / name).is_file(), name)
        verification = json.loads((SAMPLE / "verification.json").read_text(encoding="utf-8"))
        self.assertEqual(verification["net_loss_cents"], 10027)
        self.assertEqual(sum(line["committed_cents"] for line in verification["lines_due_vs_committed"]), verification["total_committed_cents"])

    def test_the_scanner_catches_planted_secrets(self):
        planted = "sk-" + "a1" * 12
        self.assertEqual(batch_ledger.scan_text(f"key {planted}"), ["sk-style API key"])
        self.assertEqual(batch_ledger.scan_keys({"headers": {"api_key": "x"}, "usage": {"completion_tokens": 3}}), [".headers.api_key"])
        self.assertIn("URL with credentials", batch_ledger.scan_text("https://user:pw@example.test/x"))


if __name__ == "__main__":
    unittest.main()
