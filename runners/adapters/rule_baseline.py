"""Adapter that runs the deterministic baseline through the same tool-turn protocol."""
import json

from ..baseline import BASELINE_VERSION, DECISION_TABLE, decide, view_from_messages
from ..protocol import Adapter, AgentTurn, ProviderMeta, ToolCall


class RuleBaselineAdapter(Adapter):
    provider = "rule_baseline"
    # Shared wire enum has no rule_baseline label yet. scripted_test means "not a model".
    execution_source = "scripted_test"
    paid = False

    def __init__(self):
        self.calls = 0

    def describe(self):
        return {"provider": self.provider, "model": "deterministic-decision-table-v0.1",
                "baseline_version": BASELINE_VERSION, "decision_table": DECISION_TABLE,
                "decision_table_signed": False, "reads_gold": False, "llm": False, "paid": False,
                "execution_source_wire": self.execution_source,
                "execution_source_note": "config_id distinguishes this program from B scripted tests and mock scenarios"}

    def next_turn(self, messages, tool_specs, runtime_state):
        del tool_specs, runtime_state
        decision = decide(view_from_messages(messages))
        meta = ProviderMeta(provider=self.provider, requested_model=BASELINE_VERSION, returned_model=BASELINE_VERSION,
                            request_id=f"rule-{self.calls + 1}", usage={"prompt_tokens": 0, "completion_tokens": 0})
        if decision.action == "finish":
            return AgentTurn("finish", text=decision.text, meta=meta,
                             assistant_message={"role": "assistant", "content": decision.text})
        calls = []
        for name, args in decision.calls:
            self.calls += 1
            calls.append(ToolCall(f"rule-call-{self.calls}", name, json.dumps(args, ensure_ascii=False)))
        message = {"role": "assistant", "content": None, "tool_calls": [
            {"id": call.call_id, "type": "function", "function": {"name": call.name, "arguments": call.arguments_text}}
            for call in calls]}
        return AgentTurn("tool_calls", tool_calls=calls, meta=meta, assistant_message=message)
