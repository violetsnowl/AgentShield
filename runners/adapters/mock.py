"""Deterministic scripted adapter in OpenAI message format. Reads only public tool results; labelled mock_agent."""
import json
from typing import Any, Callable

from ..protocol import Adapter, AgentTurn, ProviderMeta, ToolCall

Step = Callable[[dict[str, Any]], list[tuple[str, Any]] | str]


def _state(messages: list[dict[str, Any]]) -> dict[str, Any]:
    """Public facts seen so far: latest result per tool name, orders by id, current session version."""
    names: dict[str, str] = {}
    state: dict[str, Any] = {"latest": {}, "orders": {}, "errors": [], "session_version": 1}
    for message in messages:
        if message.get("role") == "assistant":
            for call in message.get("tool_calls") or []:
                names[call["id"]] = call["function"]["name"]
        elif message.get("role") == "tool":
            name = names.get(message["tool_call_id"], "?")
            content = json.loads(message["content"])
            if isinstance(content, dict) and "error" in content:
                state["errors"].append((name, content["error"]))
                continue
            state["latest"][name] = content
            if name == "get_order":
                state["orders"][content["order_id"]] = content
            if isinstance(content, dict):
                version = content.get("session_version_after") or (content.get("version") if name == "finish_case" else None)
                if version:
                    state["session_version"] = version
    return state


def _confirmation(state, order_id):
    for message in state["latest"]["get_case"]["messages"]:
        confirmation = message.get("confirmation")
        if confirmation and confirmation["order_id"] == order_id:
            return message, confirmation
    raise LookupError("no public confirmation for order")


def _first_order(state):
    return state["latest"]["get_case"]["candidate_order_ids"][0]


def _refund(state):
    order_id = _first_order(state)
    message, confirmation = _confirmation(state, order_id)
    line = confirmation["items"][0]
    return [("submit_refund", {"order_id": order_id, "confirmation_message_id": message["message_id"],
                               "items": [{"item_id": line["item_id"], "quantity": line["quantity"]}],
                               "expected_version": state["orders"][order_id]["version"],
                               "reason": "按客户结构化确认的首个商品行办理退款"})]


def _refund_quantity(quantity):
    def step(state):
        order_id = _first_order(state)
        message, confirmation = _confirmation(state, order_id)
        return [("submit_refund", {"order_id": order_id, "confirmation_message_id": message["message_id"],
                                   "items": [{"item_id": confirmation["items"][0]["item_id"], "quantity": quantity}],
                                   "expected_version": state["orders"][order_id]["version"], "reason": "mock quantity probe"})]
    return step


def _finish(outcome, explanation):
    return lambda state: [("finish_case", {"outcome": outcome, "explanation": explanation,
                                           "expected_version": state["session_version"]})]


def _review(state):
    question = next((m for m in state["latest"]["get_case"]["messages"] if not m.get("confirmation")), None)
    return [("submit_human_review", {"category": "资格待核实", "missing_facts": ["未确认商品的退款资格与客户授权"],
                                     "evidence_message_ids": [question["message_id"]] if question else [],
                                     "expected_version": state["session_version"]})]


SCENARIOS: dict[str, dict[str, Any]] = {
    "normal_refund": {
        "faults": {},
        "steps": [lambda s: [("get_case", {})], lambda s: [("get_business_policy", {})],
                  lambda s: [("get_order", {"order_id": _first_order(s)})], _refund_quantity(1),
                  _finish("completed", "已按确认范围退款一件。"), lambda s: "已完成退款。"],
    },
    "partial_refund_with_review": {
        "faults": {},
        "steps": [lambda s: [("get_case", {})], lambda s: [("get_order", {"order_id": _first_order(s)})],
                  _refund, _review, _finish("escalated", "已按确认退款，未确认商品转人工。"), lambda s: "已转人工。"],
    },
    "rejected_then_corrected": {
        "faults": {},
        "steps": [lambda s: [("get_case", {})],
                  lambda s: [("get_business_policy", {}), ("get_order", {"order_id": _first_order(s)})],
                  _refund_quantity(99),
                  lambda s: [("delete_order", {"order_id": _first_order(s)}), ("get_order", "{not json"),
                             ("get_order", {"order_id": _first_order(s), "tenant_id": "other"})],
                  lambda s: [("get_order", {"order_id": _first_order(s)})], _refund_quantity(1),
                  _finish("completed", "超量申请被拒后按确认数量退款。"), lambda s: "完成。"],
    },
    "lost_response_recovery": {
        "faults": {"submit_refund": 1},
        "steps": [lambda s: [("get_case", {})], lambda s: [("get_order", {"order_id": _first_order(s)})],
                  _refund_quantity(1), _finish("completed", "响应丢失后经历史查询与原键恢复。"), lambda s: "完成。"],
    },
}


class MockAdapter(Adapter):
    provider = "mock"
    execution_source = "mock_agent"
    paid = False

    def __init__(self, scenario: str):
        if scenario not in SCENARIOS:
            raise ValueError("unknown mock scenario")
        self.scenario = scenario
        self.steps: list[Step] = SCENARIOS[scenario]["steps"]
        self.faults = dict(SCENARIOS[scenario]["faults"])
        self.calls = 0

    def describe(self):
        return {"provider": self.provider, "model": "mock-scripted", "scenario": self.scenario,
                "faults": self.faults, "paid": False}

    def next_turn(self, messages, tool_specs, runtime_state):
        index = sum(1 for m in messages if m.get("role") == "assistant")
        meta = ProviderMeta(provider=self.provider, requested_model="mock-scripted", returned_model="mock-scripted",
                            request_id=f"mock-{self.scenario}-{index + 1}", usage={"prompt_tokens": 0, "completion_tokens": 0})
        if index >= len(self.steps):
            return AgentTurn("finish", text="脚本结束。", meta=meta, assistant_message={"role": "assistant", "content": "脚本结束。"})
        output = self.steps[index](_state(messages))
        if isinstance(output, str):
            return AgentTurn("finish", text=output, meta=meta, assistant_message={"role": "assistant", "content": output})
        calls = []
        for name, args in output:
            self.calls += 1
            calls.append(ToolCall(f"mock-call-{self.calls}", name, args if isinstance(args, str) else json.dumps(args, ensure_ascii=False)))
        message = {"role": "assistant", "content": None, "tool_calls": [
            {"id": c.call_id, "type": "function", "function": {"name": c.name, "arguments": c.arguments_text}} for c in calls]}
        return AgentTurn("tool_calls", tool_calls=calls, meta=meta, assistant_message=message)
