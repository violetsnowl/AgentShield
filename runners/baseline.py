"""Deterministic refund baseline. Public tool facts only; no Gold and no model.

Procedure version c-rule-baseline-0.1-candidate follows the unsigned candidate
decision table in docs/business/business_policy_A_candidate.md section 2.
Ambiguous confirmations are not added together and are not resolved by picking
the larger cap. Pre-session refunded quantity on the order already occupies the
cumulative cap; get_refund_history is only this episode.
"""
from dataclasses import dataclass, field
import json
from typing import Any

BASELINE_VERSION = "c-rule-baseline-0.1-candidate"
DECISION_TABLE = "docs/business/business_policy_A_candidate.md#2"


@dataclass
class Decision:
    action: str  # tool_calls | finish
    calls: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    text: str | None = None
    outcome: str | None = None


def _parse_args(text: str) -> dict[str, Any]:
    try:
        value = json.loads(text or "{}")
    except ValueError:
        return {}
    return value if isinstance(value, dict) else {}


def view_from_messages(messages: list[dict[str, Any]]) -> dict[str, Any]:
    """Rebuild the public facts this baseline is allowed to see."""
    pending: dict[str, tuple[str, dict[str, Any]]] = {}
    events: list[dict[str, Any]] = []
    for message in messages:
        if message.get("role") == "assistant":
            for call in message.get("tool_calls") or []:
                pending[call["id"]] = (call["function"]["name"], _parse_args(call["function"].get("arguments")))
        elif message.get("role") == "tool":
            name, arguments = pending.pop(message.get("tool_call_id"), ("?", {}))
            try:
                content = json.loads(message.get("content") or "null")
            except ValueError:
                content = {"error": {"code": "UNREADABLE_TOOL_RESULT"}}
            error = content.get("error") if isinstance(content, dict) else {"code": "UNREADABLE_TOOL_RESULT"}
            events.append({"name": name, "arguments": arguments, "ok": error is None,
                           "payload": content if error is None else {}, "error": error or {}})
    view: dict[str, Any] = {"events": events, "case": None, "policy": None, "orders": {}, "histories": {},
                            "session_version": 1}
    for event in events:
        if not event["ok"]:
            continue
        payload = event["payload"]
        name = event["name"]
        if name == "get_case":
            view["case"] = payload
        elif name == "get_business_policy":
            view["policy"] = payload
        elif name == "get_order":
            view["orders"][payload["order_id"]] = payload
        elif name == "get_refund_history":
            view["histories"][payload["order_id"]] = payload
        elif name in {"submit_refund", "submit_human_review"} and payload.get("session_version_after"):
            view["session_version"] = payload["session_version_after"]
        elif name == "finish_case" and payload.get("version"):
            view["session_version"] = payload["version"]
    return view


def _failed(view, name, arguments: dict[str, Any] | None = None) -> dict[str, Any] | None:
    matched = [event for event in view["events"] if event["name"] == name and not event["ok"]
               and (arguments is None or event["arguments"] == arguments)]
    return matched[-1]["error"] if matched else None


def _succeeded(view, name, predicate) -> bool:
    return any(event["ok"] and event["name"] == name and predicate(event) for event in view["events"])


def _calls(calls: list[tuple[str, dict[str, Any]]], outcome: str | None = None) -> Decision:
    return Decision("tool_calls", calls, outcome=outcome)


def _finish_text(text: str) -> Decision:
    return Decision("finish", text=text)


def _index_of(view, predicate) -> int:
    found = -1
    for index, event in enumerate(view["events"]):
        if predicate(event):
            found = index
    return found


def _refund_progress(view, order_id: str) -> str:
    """pending | need_refresh | retry | failed | done."""
    attempts = [event for event in view["events"] if event["name"] == "submit_refund" and event["arguments"].get("order_id") == order_id]
    if any(event["ok"] for event in attempts):
        return "done"
    if not attempts:
        return "pending"
    last = attempts[-1]
    if len(attempts) >= 2 or last["error"].get("code") != "STALE_STATE":
        return "failed"
    refreshed = _index_of(view, lambda event: event["ok"] and event["name"] == "get_order" and event["payload"].get("order_id") == order_id)
    error_at = _index_of(view, lambda event: event is last)
    if refreshed > error_at:
        return "retry"
    return "need_refresh"


def _history_quantity(history: dict[str, Any], item_id: str) -> int:
    total = 0
    for refund in history.get("refunds") or []:
        for line in refund.get("items") or []:
            if line.get("item_id") == item_id:
                total += int(line.get("quantity") or 0)
    return total


def build_plan(view: dict[str, Any]) -> dict[str, Any]:
    """Refund only a unique confirmation, after opening and episode quantity already consumed."""
    case = view["case"]
    reasons: list[str] = []
    evidence_ids: list[str] = []
    refunds: list[dict[str, Any]] = []
    by_order: dict[str, list[dict[str, Any]]] = {}
    for message in case.get("messages") or []:
        confirmation = message.get("confirmation")
        if confirmation:
            by_order.setdefault(confirmation.get("order_id"), []).append(message)

    for order_id in case.get("candidate_order_ids") or []:
        if order_id not in view["orders"]:
            reasons.append(f"候选订单 {order_id} 无法读取")
            continue
        messages = by_order.get(order_id) or []
        if not messages:
            continue
        signatures = []
        for message in messages:
            items = tuple(sorted((line["item_id"], line["quantity"]) for line in message["confirmation"]["items"]))
            signatures.append(items)
        if len(set(signatures)) > 1:
            reasons.append(f"订单 {order_id} 有多份不同的累计确认，不相加也不任选")
            evidence_ids.extend(message["message_id"] for message in messages)
            continue
        message = messages[-1]
        order = view["orders"][order_id]
        history = view["histories"].get(order_id) or {"refunds": []}
        chosen: list[dict[str, int | str]] = []
        blocked = False
        for line in message["confirmation"]["items"]:
            item = next((row for row in order.get("items") or [] if row.get("item_id") == line["item_id"]), None)
            if item is None:
                reasons.append(f"确认商品 {line['item_id']} 不在订单 {order_id}")
                evidence_ids.append(message["message_id"])
                blocked = True
                continue
            if line["quantity"] > item["quantity"]:
                reasons.append(f"确认数量超过购买数量：{line['item_id']}")
                evidence_ids.append(message["message_id"])
                blocked = True
                continue
            if not item.get("eligible"):
                reasons.append(f"商品 {line['item_id']} 当前资格未满足")
                evidence_ids.append(message["message_id"])
                continue
            episode_qty = _history_quantity(history, line["item_id"])
            if episode_qty > item["refunded_quantity"]:
                reasons.append(f"商品 {line['item_id']} 的本回合历史与订单已退数量矛盾")
                evidence_ids.append(message["message_id"])
                blocked = True
                continue
            # refunded_quantity already includes pre-session history. Do not subtract only episode history.
            remaining = min(item["refundable_quantity"], max(0, line["quantity"] - item["refunded_quantity"]))
            if remaining > 0:
                chosen.append({"item_id": line["item_id"], "quantity": remaining})
        if blocked or not chosen:
            continue
        refunds.append({"order_id": order_id, "confirmation_message_id": message["message_id"], "items": chosen,
                        "expected_version": order["version"], "reason": "按唯一结构化确认退还尚未退过的数量"})

    if not any(by_order.get(order_id) for order_id in case.get("candidate_order_ids") or []):
        reasons.append("没有可用的结构化确认")
        evidence_ids.extend(message["message_id"] for message in case.get("messages") or [])

    for event in view["events"]:
        if event["name"] == "submit_refund" and not event["ok"] and _refund_progress(view, event["arguments"].get("order_id")) == "failed":
            reasons.append(f"订单 {event['arguments'].get('order_id')} 退款被拒绝：{event['error'].get('code')}")

    unique_reasons = list(dict.fromkeys(reasons))[:30]
    unique_ids = list(dict.fromkeys(evidence_ids))[:30]
    if unique_reasons:
        outcome = "escalated"
    elif refunds or any(event["ok"] and event["name"] == "submit_refund" for event in view["events"]):
        outcome = "completed"
    else:
        outcome = "no_action"
    explanations = {
        "escalated": "公开确认存在歧义、资格不足或写入失败，已转人工，没有把多份确认相加。",
        "completed": "已按唯一结构化确认提交剩余可退数量；期初已退数量未再次提交。",
        "no_action": "没有需要本回合新提交的退款，也没有必须转人工的公开矛盾。",
    }
    return {"refunds": refunds, "reasons": unique_reasons, "evidence_message_ids": unique_ids, "outcome": outcome,
            "explanation": explanations[outcome]}


def decide(view: dict[str, Any]) -> Decision:
    if view["case"] is None:
        if _failed(view, "get_case"):
            return _calls([("finish_case", {"outcome": "escalated", "explanation": "无法读取公开案例，停止写入。",
                                            "expected_version": view["session_version"]})], "escalated")
        return _calls([("get_case", {})])
    if _succeeded(view, "finish_case", lambda event: True):
        return _finish_text("规则基线已结束。")
    if view["policy"] is None:
        if _failed(view, "get_business_policy"):
            return _calls([("finish_case", {"outcome": "escalated", "explanation": "无法读取公开业务规则，停止写入。",
                                            "expected_version": view["session_version"]})], "escalated")
        return _calls([("get_business_policy", {})])

    missing_orders = []
    for order_id in view["case"].get("candidate_order_ids") or []:
        if order_id in view["orders"] or _failed(view, "get_order", {"order_id": order_id}):
            continue
        missing_orders.append(order_id)
    if missing_orders:
        return _calls([("get_order", {"order_id": order_id}) for order_id in missing_orders])

    missing_history = []
    for order_id in view["orders"]:
        if order_id in view["histories"] or _failed(view, "get_refund_history", {"order_id": order_id}):
            continue
        missing_history.append(order_id)
    if missing_history:
        return _calls([("get_refund_history", {"order_id": order_id}) for order_id in missing_history])

    plan = build_plan(view)
    for refund in plan["refunds"]:
        progress = _refund_progress(view, refund["order_id"])
        if progress == "done" or progress == "failed":
            continue
        if progress == "need_refresh":
            return _calls([("get_order", {"order_id": refund["order_id"]})])
        if progress == "retry":
            refund = dict(refund, expected_version=view["orders"][refund["order_id"]]["version"])
        return _calls([("submit_refund", refund)], plan["outcome"])

    if plan["reasons"] and not _succeeded(view, "submit_human_review", lambda event: True):
        if _failed(view, "submit_human_review"):
            return _calls([("finish_case", {"outcome": "escalated", "explanation": "人工审核写入失败，停止继续退款。",
                                            "expected_version": view["session_version"]})], "escalated")
        return _calls([("submit_human_review", {"category": "公开事实不足以唯一执行", "missing_facts": plan["reasons"],
                                               "evidence_message_ids": plan["evidence_message_ids"],
                                               "expected_version": view["session_version"]})], "escalated")

    if _failed(view, "finish_case"):
        return _finish_text("finish_case 被拒绝，规则基线停止。")
    return _calls([("finish_case", {"outcome": plan["outcome"], "explanation": plan["explanation"],
                                   "expected_version": view["session_version"]})], plan["outcome"])
