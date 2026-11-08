"""A batch's thinking state is read from provider usage, because a request parameter can be ignored."""
import json
import tempfile
import unittest
from pathlib import Path

from workbench.claim_cases import VOIDED_CONFIG_SUFFIX, _thinking_label
from experiments.check_reasoning import matches, reasoning_summary

ROOT = Path(__file__).resolve().parents[1]
LOW_CONFIGS = ("mimo", "deepseek", "glm", "qwen")


def turn(reasoning, completion=100):
    return json.dumps({"kind": "model_response", "usage": {"completion_tokens": completion,
                                                           "completion_tokens_details": {"reasoning_tokens": reasoning}}})


class ReasoningSummaryTests(unittest.TestCase):
    def batch(self, *runs):
        folder = tempfile.TemporaryDirectory(dir=ROOT / "var")
        self.addCleanup(folder.cleanup)
        root = Path(folder.name)
        for index, lines in enumerate(runs):
            run = root / f"run{index}"
            run.mkdir()
            (run / "attempts.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
        return root

    def test_counts_turns_and_tokens_from_usage(self):
        summary = reasoning_summary(self.batch([turn(40), turn(0)], [turn(60), json.dumps({"kind": "episode_stop"})]))
        self.assertEqual((summary["runs"], summary["turns"], summary["turns_with_reasoning"], summary["reasoning_tokens"]), (2, 3, 2, 100))
        self.assertEqual(summary["reasoning_tokens_per_run"], 50.0)

    def test_a_batch_that_claims_off_fails_when_any_reasoning_appears(self):
        leaked = reasoning_summary(self.batch([turn(0), turn(7)]))
        self.assertFalse(matches(leaked, "off"))
        self.assertTrue(matches(leaked, "on"))
        self.assertTrue(matches(reasoning_summary(self.batch([turn(0)])), "off"))

    def test_a_batch_without_usage_proves_nothing(self):
        empty = reasoning_summary(self.batch([json.dumps({"kind": "episode_stop"})]))
        self.assertFalse(matches(empty, "off"))
        self.assertFalse(matches(empty, "on"))


class SameSettingTests(unittest.TestCase):
    def configs(self):
        return {name: json.loads((ROOT / f"configs/runner/commandcode-{name}-low-risk-v0.2.json").read_text(encoding="utf-8"))
                for name in LOW_CONFIGS}

    def test_only_the_model_and_its_price_differ(self):
        configs = self.configs()
        strip = lambda config: {key: value for key, value in config.items() if key not in ("config_id", "config_version", "model", "pricing", "notes")}
        self.assertEqual(len({json.dumps(strip(config), sort_keys=True) for config in configs.values()}), 1)
        self.assertEqual(len({config["model"] for config in configs.values()}), 4)

    def test_every_model_asks_for_the_same_thinking_effort(self):
        for config in self.configs().values():
            self.assertEqual(config["request_params"], {"reasoning_effort": "low", "temperature": 0})
            self.assertEqual(config["api_key_env"], "COMMANDCODE_API_KEY")
            self.assertEqual(config["base_url"], "https://api.commandcode.ai/provider/v1")

    def test_a_long_decision_is_not_cut_off(self):
        # Reasoning counts toward max_tokens. At 2048 a model could spend the whole cap thinking and never act.
        for config in self.configs().values():
            self.assertGreaterEqual(config["budget"]["max_output_tokens"], 8192)
            self.assertGreaterEqual(config["budget"]["api_timeout_s"], 300)



class SameRouteThinkingTests(unittest.TestCase):
    def configs(self):
        return {name: json.loads((ROOT / f"configs/runner/mimo-direct-{name}-risk-v0.2.json").read_text(encoding="utf-8")) for name in ("off", "low")}

    def test_only_the_thinking_setting_differs(self):
        configs = self.configs()
        strip = lambda config: {key: value for key, value in config.items() if key not in ("config_id", "config_version", "request_params")}
        self.assertEqual(strip(configs["off"]), strip(configs["low"]))
        self.assertEqual(configs["off"]["request_params"], {"thinking": {"type": "disabled"}, "temperature": 0})
        self.assertEqual(configs["low"]["request_params"], {"reasoning_effort": "low", "temperature": 0})

    def test_it_matches_the_four_model_round_apart_from_the_route(self):
        reference = json.loads((ROOT / "configs/runner/commandcode-mimo-low-risk-v0.2.json").read_text(encoding="utf-8"))
        for config in self.configs().values():
            for key in ("budget", "prompt_file", "prompt_version", "kickoff"):
                self.assertEqual(config[key], reference[key])
            self.assertEqual(config["model"], reference["model"].split("/")[-1])

    def test_the_workbench_keeps_and_labels_both_arms(self):
        labels = {name: _thinking_label(config["config_id"]) for name, config in self.configs().items()}
        self.assertEqual(labels, {"off": "关思考", "low": "低思考"})
        for config in self.configs().values():
            self.assertFalse(config["config_id"].endswith(VOIDED_CONFIG_SUFFIX))
