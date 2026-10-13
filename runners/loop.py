"""Run one episode: adapter turns -> whitelist validation -> HTTP to B -> results back, under hard budgets."""
from dataclasses import asdict, dataclass, field
import json
import time
from typing import Any

from .attempts import AttemptLog
from .protocol import Adapter, AgentTurn
from .sandbox_client import SessionTransport, Transport
from .tools import WRITE_TOOLS, LocalRejection, validate_call


@dataclass
class Budget:
    max_turns: int = 12
    max_tool_calls: int = 24
    api_timeout_s: float = 60.0
    run_timeout_s: float = 300.0
    api_retries: int = 2
    transport_retries: int = 2
    max_total_tokens: int = 80000
    max_output_tokens: int = 2048
    max_run_cost_cny: float | None = None

    @classmethod
    def from_mapping(cls, raw: dict[str, Any]) -> "Budget":
        unknown = set(raw) - set(cls.__dataclass_fields__)
        if unknown:
            raise ValueError("Unknown budget fields: " + ", ".join(sorted(unknown)))
        return cls(**raw)


@dataclass
class Pricing:
    """CNY per million tokens. None means unknown; cost is then reported as null, never 0."""
    input_per_million: float | None = None
    output_per_million: float | None = None
    basis: str = "unknown"

    def cost(self, prompt_tokens: int, completion_tokens: int) -> float | None:
        if self.input_per_million is None or self.output_per_million is None:
            return None
        return (prompt_tokens * self.input_per_million + completion_tokens * self.output_per_million) / 1_000_000


@dataclass
class EpisodeResult:
    run_status: str = "started"  # completed | truncated | infra_error
    stop_reason: str | None = None
    turns: int = 0
    tool_calls_requested: int = 0
    tool_calls_dispatched: int = 0
    local_rejections: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_cny: float | None = 0.0
    cost_basis: str = "not_applicable"
    elapsed_s: float = 0.0
    final_text: str | None = None
    provider_calls: list[dict[str, Any]] = field(default_factory=list)
    unresolved_write: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class Executor:
    """Executes one validated call with run-owned idempotency keys and the B recovery protocol."""

    def __init__(self, session: SessionTransport, log: AttemptLog, run_tag: str, transport_retries: int):
        self.session = session
        self.log = log
        self.run_tag = run_tag
        self.transport_retries = transport_retries
        self.counter = 0

    def _send(self, name, args, key, call_id, purpose, model_call_id):
        self.log.record("dispatch", tool_name=name, purpose=purpose, model_call_id=model_call_id, x_call_id=call_id,
                        idempotency_key=key, arguments=args, sent=True)
        result = self.session.tool(name, args, idempotency_key=key, call_id=call_id)
        error_code = result.payload.get("code") if isinstance(result.payload, dict) and (result.http_status or 0) >= 400 else None
        self.log.record("dispatch_result", tool_name=name, purpose=purpose, x_call_id=call_id, outcome=result.outcome,
                        http_status=result.http_status, b_request_id=result.request_id, error_code=error_code,
                        detail=result.detail, transaction_id=(result.payload or {}).get("transaction_id") if isinstance(result.payload, dict) else None,
                        ticket_id=(result.payload or {}).get("ticket_id") if isinstance(result.payload, dict) else None)
        return result

    def execute(self, name: str, args: dict[str, Any], model_call_id: str) -> tuple[Transport, bool]:
        """Return (transport, resolved). resolved=False means a write's commit state is still unknown."""
        self.counter += 1
        call_id = f"c.{self.run_tag}.{self.counter}"
        key = f"ck.{self.run_tag}.{self.counter}" if name in WRITE_TOOLS else None
        result = self._send(name, args, key, call_id, "model_call", model_call_id)
        for retry in range(self.transport_retries):
            if not result.unknown:
                return result, True
            if name == "submit_refund":
                probe = self._send("get_refund_history", {"order_id": args["order_id"], "idempotency_key": key},
                                   None, f"{call_id}.probe{retry + 1}", "recovery_history_probe", model_call_id)
                state = probe.payload.get("request_status") if probe.outcome == "response" and isinstance(probe.payload, dict) else None
                self.log.record("recovery_decision", tool_name=name, idempotency_key=key, history_request_status=state,
                                action="replay_same_key_same_arguments")
            result = self._send(name, args, key, f"{call_id}.r{retry + 1}", "transport_retry_same_key", model_call_id)
        return result, not result.unknown


def _tool_message(call_id: str, content: Any) -> dict[str, Any]:
    return {"role": "tool", "tool_call_id": call_id, "content": json.dumps(content, ensure_ascii=False)}


def run_episode(adapter: Adapter, session: SessionTransport, log: AttemptLog, *, system_prompt: str,
                kickoff: str, tool_specs: list[dict[str, Any]], budget: Budget, pricing: Pricing,
                run_tag: str, remaining_cost_cny: float | None = None) -> tuple[EpisodeResult, list[dict[str, Any]]]:
    result = EpisodeResult(cost_basis=pricing.basis if adapter.paid else "not_applicable")
    messages: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}, {"role": "user", "content": kickoff}]
    executor = Executor(session, log, run_tag, budget.transport_retries)
    started = time.monotonic()
    last_prompt = 0

    def stop(status, reason):
        result.run_status, result.stop_reason = status, reason
        log.record("episode_stop", run_status=status, stop_reason=reason)

    while True:
        result.elapsed_s = round(time.monotonic() - started, 3)
        if result.turns >= budget.max_turns:
            stop("truncated", "budget_max_turns"); break
        if result.elapsed_s >= budget.run_timeout_s:
            stop("truncated", "budget_run_timeout"); break
        reserve_tokens = last_prompt + 2000 + budget.max_output_tokens
        if result.prompt_tokens + result.completion_tokens + reserve_tokens > budget.max_total_tokens and result.turns:
            stop("truncated", "budget_max_total_tokens"); break
        if adapter.paid:
            reserve_cost = pricing.cost(last_prompt + 2000, budget.max_output_tokens)
            spent = result.cost_cny or 0.0
            for cap, reason in ((budget.max_run_cost_cny, "budget_run_cost"), (remaining_cost_cny, "budget_global_cost")):
                if cap is not None and reserve_cost is not None and spent + reserve_cost > cap:
                    stop("truncated", reason)
                    break
            if result.stop_reason:
                break

        log.record("model_request", turn=result.turns + 1, message_count=len(messages))
        turn: AgentTurn = adapter.next_turn(messages, tool_specs, {"turn": result.turns + 1, "budget": asdict(budget)})
        result.turns += 1
        meta = turn.meta
        if meta:
            usage = meta.usage or {}
            p, c = int(usage.get("prompt_tokens") or 0), int(usage.get("completion_tokens") or 0)
            result.prompt_tokens += p
            result.completion_tokens += c
            last_prompt = p or last_prompt
            if adapter.paid:
                turn_cost = pricing.cost(p, c)
                result.cost_cny = None if turn_cost is None or result.cost_cny is None else round(result.cost_cny + turn_cost, 6)
            result.provider_calls.append(asdict(meta))
        log.record("model_response", turn=result.turns, status=turn.status, error_code=turn.error_code,
                   tool_calls=[{"call_id": c.call_id, "name": c.name} for c in turn.tool_calls],
                   provider_request_id=meta.request_id if meta else None, usage=meta.usage if meta else None)

        if turn.status == "error":
            stop("infra_error", "provider_" + (turn.error_code or "error")); break
        if turn.assistant_message:
            messages.append(turn.assistant_message)
        if turn.status == "finish":
            result.final_text = turn.text
            stop("completed", "final_text"); break

        finished = False
        for call in turn.tool_calls:
            result.tool_calls_requested += 1
            if result.tool_calls_requested > budget.max_tool_calls:
                log.record("local_rejection", tool_name=call.name, model_call_id=call.call_id, code="BUDGET_TOOL_CALLS", sent=False)
                messages.append(_tool_message(call.call_id, {"error": {"code": "BUDGET_TOOL_CALLS", "message": "Tool-call budget exhausted.", "retryable": False}}))
                continue
            try:
                args = validate_call(call.name, call.arguments_text)
            except LocalRejection as rejection:
                result.local_rejections += 1
                log.record("local_rejection", tool_name=call.name[:128], model_call_id=call.call_id, code=rejection.code,
                           message=rejection.message, sent=False)
                messages.append(_tool_message(call.call_id, {"error": rejection.payload()}))
                continue
            result.tool_calls_dispatched += 1
            transport, resolved = executor.execute(call.name, args, call.call_id)
            if not resolved:
                result.unresolved_write = {"tool_name": call.name, "model_call_id": call.call_id, "outcome": transport.outcome}
                messages.append(_tool_message(call.call_id, {"error": {"code": "TRANSPORT_UNKNOWN", "message": "Result unknown; runner stopped.", "retryable": False}}))
                stop("infra_error", "transport_unknown_after_recovery")
                finished = True
                break
            if (transport.http_status or 0) >= 400:
                messages.append(_tool_message(call.call_id, {"error": transport.payload}))
            else:
                messages.append(_tool_message(call.call_id, transport.payload))
                if call.name == "finish_case":
                    finished = True
        if result.stop_reason:
            break
        if finished:
            # Remaining calls in the same turn still received answers above; the case is closed in B.
            result.final_text = None
            stop("completed", "finish_case_tool"); break
        if result.tool_calls_requested > budget.max_tool_calls:
            stop("truncated", "budget_max_tool_calls"); break

    result.elapsed_s = round(time.monotonic() - started, 3)
    return result, messages
