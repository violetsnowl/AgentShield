"""Unified turn protocol shared by every adapter (V1.1 section 7.1)."""
from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass
class ToolCall:
    call_id: str
    name: str
    arguments_text: str


@dataclass
class ProviderMeta:
    provider: str
    requested_model: str
    returned_model: str | None = None
    request_id: str | None = None
    usage: dict[str, Any] | None = None
    finish_reason: str | None = None
    latency_ms: int | None = None
    http_attempts: int = 0


@dataclass
class AgentTurn:
    status: Literal["tool_calls", "finish", "error"]
    tool_calls: list[ToolCall] = field(default_factory=list)
    text: str | None = None
    error_code: str | None = None
    error_detail: str | None = None
    meta: ProviderMeta | None = None
    # Public OpenAI-format assistant message appended to the shared transcript.
    assistant_message: dict[str, Any] | None = None


class Adapter:
    """next_turn(public_messages, tool_specs, runtime_state) -> AgentTurn."""
    provider = "abstract"
    execution_source = "mock_agent"
    paid = False

    def describe(self) -> dict[str, Any]:
        raise NotImplementedError

    def next_turn(self, messages: list[dict[str, Any]], tool_specs: list[dict[str, Any]],
                  runtime_state: dict[str, Any]) -> AgentTurn:
        raise NotImplementedError
