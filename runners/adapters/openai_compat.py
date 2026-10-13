"""OpenAI-compatible Chat Completions adapter (DeepSeek first). Private reasoning stays inside this object."""
import json
import time
from typing import Any

import httpx

from ..protocol import Adapter, AgentTurn, ProviderMeta, ToolCall

RETRYABLE_STATUS = {408, 409, 429, 500, 502, 503, 504}


class OpenAICompatibleAdapter(Adapter):
    execution_source = "observed_agent_execution"
    paid = True

    def __init__(self, *, provider: str, base_url: str, model: str, api_key: str, request_params: dict[str, Any],
                 max_output_tokens: int, api_timeout_s: float, api_retries: int, unsupported_params: list[str],
                 http_client: httpx.Client | None = None, retry_sleep_s: float = 2.0):
        if not base_url.startswith("https://"):
            raise ValueError("Provider base_url must be https")
        self.provider = provider
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._api_key = api_key
        self.request_params = dict(request_params)
        self.max_output_tokens = max_output_tokens
        self.api_timeout_s = api_timeout_s
        self.api_retries = api_retries
        self.unsupported_params = unsupported_params
        # id(assistant message) -> reasoning_content. Needed for provider continuation, never published.
        self._private_reasoning: dict[int, str] = {}
        self.private_reasoning_turns = 0
        self.retry_sleep_s = retry_sleep_s
        self._client = http_client or httpx.Client(timeout=api_timeout_s, trust_env=False)

    def describe(self):
        return {"provider": self.provider, "base_url": self.base_url, "model": self.model,
                "request_params": self.request_params, "max_output_tokens": self.max_output_tokens,
                "unsupported_params": self.unsupported_params, "paid": True,
                "private_reasoning_policy": "kept in adapter memory for continuation; not logged or exported"}

    def _wire_messages(self, messages):
        out = []
        for message in messages:
            reasoning = self._private_reasoning.get(id(message))
            out.append({**message, "reasoning_content": reasoning} if reasoning is not None else message)
        return out

    def next_turn(self, messages, tool_specs, runtime_state):
        body = {"model": self.model, "messages": self._wire_messages(messages), "tools": tool_specs,
                "tool_choice": "auto", "max_tokens": self.max_output_tokens, "stream": False, **self.request_params}
        meta = ProviderMeta(provider=self.provider, requested_model=self.model)
        headers = {"Authorization": "Bearer " + self._api_key, "Content-Type": "application/json"}
        started = time.monotonic()
        response = None
        for attempt in range(self.api_retries + 1):
            meta.http_attempts = attempt + 1
            try:
                response = self._client.post(self.base_url + "/chat/completions", headers=headers, json=body)
            except httpx.TimeoutException:
                response = None
                code = "PROVIDER_TIMEOUT"
            except httpx.HTTPError as error:
                response = None
                code = "PROVIDER_CONNECTION_" + type(error).__name__
            else:
                if response.status_code < 400:
                    break
                code = f"PROVIDER_HTTP_{response.status_code}"
                if response.status_code not in RETRYABLE_STATUS:
                    break
            if attempt < self.api_retries:
                time.sleep(self.retry_sleep_s * (attempt + 1))
        meta.latency_ms = int((time.monotonic() - started) * 1000)
        if response is None or response.status_code >= 400:
            detail = None
            if response is not None:
                try:
                    detail = json.dumps(response.json().get("error", {}), ensure_ascii=False)[:500]
                except ValueError:
                    detail = response.text[:300]
            return AgentTurn("error", error_code=code, error_detail=detail, meta=meta)
        try:
            data = response.json()
            choice = data["choices"][0]
            message = choice["message"]
        except (ValueError, KeyError, IndexError, TypeError):
            return AgentTurn("error", error_code="PROVIDER_BAD_RESPONSE", meta=meta)
        meta.returned_model = data.get("model")
        meta.request_id = data.get("id") or response.headers.get("x-request-id")
        meta.usage = data.get("usage")
        meta.finish_reason = choice.get("finish_reason")
        public = {"role": "assistant", "content": message.get("content")}
        raw_calls = message.get("tool_calls") or []
        if raw_calls:
            public["tool_calls"] = [{"id": c["id"], "type": "function",
                                     "function": {"name": c["function"]["name"], "arguments": c["function"].get("arguments") or "{}"}}
                                    for c in raw_calls]
        if message.get("reasoning_content") is not None:
            self._private_reasoning[id(public)] = message["reasoning_content"]
            self.private_reasoning_turns += 1
        if raw_calls:
            calls = [ToolCall(c["id"], c["function"]["name"], c["function"].get("arguments") or "{}") for c in raw_calls]
            return AgentTurn("tool_calls", tool_calls=calls, text=message.get("content"), meta=meta, assistant_message=public)
        if meta.finish_reason == "length":
            return AgentTurn("error", error_code="OUTPUT_TRUNCATED_LENGTH", meta=meta, assistant_message=public)
        return AgentTurn("finish", text=message.get("content") or "", meta=meta, assistant_message=public)
