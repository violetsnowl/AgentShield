"""OpenAI-compatible adapter against a local httpx MockTransport: no network, no key, no cost."""
import json
import unittest

import httpx

from runners.adapters.openai_compat import OpenAICompatibleAdapter


def adapter(handler, retries=2):
    return OpenAICompatibleAdapter(
        provider="deepseek", base_url="https://api.example.invalid", model="deepseek-flash", api_key="sk-test-not-real",
        request_params={"thinking": {"type": "disabled"}}, max_output_tokens=256, api_timeout_s=5, api_retries=retries,
        unsupported_params=[], http_client=httpx.Client(transport=httpx.MockTransport(handler)), retry_sleep_s=0)


def completion(message, finish="tool_calls"):
    return httpx.Response(200, json={"id": "resp-1", "model": "deepseek-flash", "usage": {"prompt_tokens": 10, "completion_tokens": 5},
                                     "choices": [{"message": message, "finish_reason": finish}]})


class AdapterTests(unittest.TestCase):
    def test_tool_call_parsed_and_private_reasoning_only_sent_back(self):
        bodies = []

        def handler(request):
            bodies.append(json.loads(request.content))
            if len(bodies) == 1:
                return completion({"role": "assistant", "content": None, "reasoning_content": "PRIVATE-THOUGHT",
                                   "tool_calls": [{"id": "call_1", "type": "function", "function": {"name": "get_case", "arguments": "{}"}}]})
            return completion({"role": "assistant", "content": "完成"}, "stop")

        a = adapter(handler)
        messages = [{"role": "system", "content": "s"}, {"role": "user", "content": "u"}]
        turn = a.next_turn(messages, [], {})
        self.assertEqual((turn.status, turn.tool_calls[0].name, turn.meta.request_id), ("tool_calls", "get_case", "resp-1"))
        self.assertNotIn("reasoning_content", turn.assistant_message)
        messages += [turn.assistant_message, {"role": "tool", "tool_call_id": "call_1", "content": "{}"}]
        final = a.next_turn(messages, [], {})
        self.assertEqual((final.status, final.text), ("finish", "完成"))
        self.assertEqual(bodies[1]["messages"][2]["reasoning_content"], "PRIVATE-THOUGHT")
        self.assertNotIn("PRIVATE-THOUGHT", json.dumps(messages, ensure_ascii=False))
        self.assertEqual(bodies[0]["thinking"], {"type": "disabled"})

    def test_retries_429_then_succeeds_and_counts_attempts(self):
        calls = []

        def handler(request):
            calls.append(1)
            return httpx.Response(429, json={"error": {"message": "rate"}}) if len(calls) < 3 else completion({"role": "assistant", "content": "ok"}, "stop")

        turn = adapter(handler).next_turn([], [], {})
        self.assertEqual((turn.status, turn.meta.http_attempts), ("finish", 3))

    def test_non_retryable_error_surfaces_code_without_key(self):
        turn = adapter(lambda r: httpx.Response(401, json={"error": {"message": "bad key"}})).next_turn([], [], {})
        self.assertEqual((turn.status, turn.error_code, turn.meta.http_attempts), ("error", "PROVIDER_HTTP_401", 1))
        self.assertNotIn("sk-test-not-real", turn.error_detail or "")

    def test_length_cutoff_is_an_error_not_a_finish(self):
        turn = adapter(lambda r: completion({"role": "assistant", "content": "半句"}, "length")).next_turn([], [], {})
        self.assertEqual((turn.status, turn.error_code), ("error", "OUTPUT_TRUNCATED_LENGTH"))


if __name__ == "__main__":
    unittest.main()
