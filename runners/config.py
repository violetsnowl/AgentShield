"""Load a runner config file and build the adapter, budget and pricing it describes."""
import hashlib
import json
from pathlib import Path
from typing import Any

from .adapters import MockAdapter, OpenAICompatibleAdapter, RuleBaselineAdapter
from .env import load_runner_env, paid_authorization
from .loop import Budget, Pricing

ROOT = Path(__file__).resolve().parents[1]


class PaidRunsNotAuthorized(RuntimeError):
    pass


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_config(path: Path) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    config["_path"] = path.resolve().relative_to(ROOT).as_posix()
    config["_sha256"] = file_sha256(path)
    prompt = ROOT / config["prompt_file"]
    config["_prompt_text"] = prompt.read_text(encoding="utf-8")
    config["_prompt_sha256"] = file_sha256(prompt)
    return config


def build(config: dict[str, Any], scenario: str | None = None):
    budget = Budget.from_mapping(config["budget"])
    pricing = Pricing(**config["pricing"]) if config.get("pricing") else Pricing()
    if config["adapter"] == "mock":
        if not scenario:
            raise ValueError("mock adapter requires a scenario")
        return MockAdapter(scenario), budget, pricing, None
    if config["adapter"] == "rule_baseline":
        if scenario:
            raise ValueError("rule baseline does not take a mock scenario")
        return RuleBaselineAdapter(), budget, pricing, None
    if config["adapter"] != "openai_compatible":
        raise ValueError("unknown adapter")
    env = load_runner_env()
    allowed, global_cap, reason = paid_authorization(env)
    if not allowed:
        raise PaidRunsNotAuthorized(reason)
    adapter = OpenAICompatibleAdapter(
        provider=config["provider"], base_url=config["base_url"], model=config["model"],
        api_key=env[config["api_key_env"]], request_params=config.get("request_params", {}),
        max_output_tokens=budget.max_output_tokens, api_timeout_s=budget.api_timeout_s,
        api_retries=budget.api_retries, unsupported_params=config.get("unsupported_params", []))
    return adapter, budget, pricing, global_cap
