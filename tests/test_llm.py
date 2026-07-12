"""Tests for OpenAILLM and OpenAIJudge using mocked OpenAI clients.

No network calls are made: the lazily-created OpenAI SDK clients are
replaced with fakes that return canned chat-completion responses.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Optional

from policyeval.judges.openai_judge import OpenAIJudge
from policyeval.llm.openai import OpenAILLM


def _chat_response(content: Optional[str]):
    """Build an object shaped like an OpenAI chat completion response."""
    message = SimpleNamespace(content=content)
    choice = SimpleNamespace(message=message)
    return SimpleNamespace(choices=[choice])


class FakeSyncClient:
    def __init__(self, content: Optional[str]):
        self._content = content
        self.calls: list[dict] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        return _chat_response(self._content)


class FakeAsyncClient:
    def __init__(self, content: Optional[str]):
        self._content = content
        self.calls: list[dict] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    async def _create(self, **kwargs):
        self.calls.append(kwargs)
        return _chat_response(self._content)


# ── OpenAILLM ────────────────────────────────────────────────────────────────


class TestOpenAILLMConstruction:
    def test_defaults(self):
        llm = OpenAILLM()
        assert llm.model == "gpt-4o"
        assert llm.temperature == 0.7

    def test_custom_config_stored(self):
        llm = OpenAILLM(
            model="anthropic/claude-3-opus",
            temperature=0.2,
            api_key="sk-test",
            base_url="http://localhost:4000",
            seed=7,
        )
        assert llm.model == "anthropic/claude-3-opus"
        assert llm.temperature == 0.2
        assert llm._api_key == "sk-test"
        assert llm._base_url == "http://localhost:4000"
        assert llm._default_kwargs == {"seed": 7}


class TestOpenAILLMComplete:
    def test_complete_sync_returns_content(self, monkeypatch):
        llm = OpenAILLM(model="gpt-4o")
        fake = FakeSyncClient("hello world")
        monkeypatch.setattr(llm, "_get_sync_client", lambda: fake)

        result = llm.complete_sync("system", "user")
        assert result == "hello world"

    def test_complete_sync_sends_messages_and_model(self, monkeypatch):
        llm = OpenAILLM(model="gpt-4o", temperature=0.3)
        fake = FakeSyncClient("ok")
        monkeypatch.setattr(llm, "_get_sync_client", lambda: fake)

        llm.complete_sync("SYS", "USR")
        call = fake.calls[0]
        assert call["model"] == "gpt-4o"
        assert call["temperature"] == 0.3
        assert call["messages"][0] == {"role": "system", "content": "SYS"}
        assert call["messages"][1] == {"role": "user", "content": "USR"}

    def test_complete_sync_none_content_becomes_empty_string(self, monkeypatch):
        llm = OpenAILLM()
        fake = FakeSyncClient(None)
        monkeypatch.setattr(llm, "_get_sync_client", lambda: fake)
        assert llm.complete_sync("s", "u") == ""

    def test_default_kwargs_forwarded(self, monkeypatch):
        llm = OpenAILLM(seed=99, top_p=0.5)
        fake = FakeSyncClient("x")
        monkeypatch.setattr(llm, "_get_sync_client", lambda: fake)
        llm.complete_sync("s", "u")
        call = fake.calls[0]
        assert call["seed"] == 99
        assert call["top_p"] == 0.5

    async def test_complete_async_returns_content(self, monkeypatch):
        llm = OpenAILLM()
        fake = FakeAsyncClient("async hello")
        monkeypatch.setattr(llm, "_get_async_client", lambda: fake)
        result = await llm.complete("system", "user")
        assert result == "async hello"


class TestOpenAILLMClientFactories:
    def test_get_sync_client_passes_api_key_and_base_url(self, monkeypatch):
        captured: dict = {}

        class FakeOpenAI:
            def __init__(self, **kwargs):
                captured.update(kwargs)

        import openai

        monkeypatch.setattr(openai, "OpenAI", FakeOpenAI)
        llm = OpenAILLM(api_key="sk-abc", base_url="http://proxy")
        client = llm._get_sync_client()
        assert isinstance(client, FakeOpenAI)
        assert captured == {"api_key": "sk-abc", "base_url": "http://proxy"}

    def test_sync_client_is_cached(self, monkeypatch):
        class FakeOpenAI:
            def __init__(self, **kwargs):
                pass

        import openai

        monkeypatch.setattr(openai, "OpenAI", FakeOpenAI)
        llm = OpenAILLM()
        first = llm._get_sync_client()
        second = llm._get_sync_client()
        assert first is second

    def test_get_async_client_passes_config_and_caches(self, monkeypatch):
        captured: dict = {}

        class FakeAsyncOpenAI:
            def __init__(self, **kwargs):
                captured.update(kwargs)

        import openai

        monkeypatch.setattr(openai, "AsyncOpenAI", FakeAsyncOpenAI)
        llm = OpenAILLM(api_key="sk-async", base_url="http://async-proxy")
        first = llm._get_async_client()
        second = llm._get_async_client()
        assert first is second
        assert captured == {"api_key": "sk-async", "base_url": "http://async-proxy"}

    def test_no_kwargs_when_api_key_and_base_url_unset(self, monkeypatch):
        captured: dict = {}

        class FakeOpenAI:
            def __init__(self, **kwargs):
                captured.update(kwargs)

        import openai

        monkeypatch.setattr(openai, "OpenAI", FakeOpenAI)
        OpenAILLM()._get_sync_client()
        assert captured == {}


class TestCompleteSyncFromAsync:
    def test_runs_async_when_no_running_loop(self, monkeypatch):
        llm = OpenAILLM()
        fake = FakeAsyncClient("bridged result")
        monkeypatch.setattr(llm, "_get_async_client", lambda: fake)
        result = llm._complete_sync_from_async("s", "u")
        assert result == "bridged result"

    async def test_runs_in_thread_when_loop_running(self, monkeypatch):
        # This test itself runs inside a running event loop (asyncio_mode=auto),
        # so the helper must offload to a worker thread.
        llm = OpenAILLM()
        fake = FakeAsyncClient("threaded result")
        monkeypatch.setattr(llm, "_get_async_client", lambda: fake)
        result = llm._complete_sync_from_async("s", "u")
        assert result == "threaded result"


# ── OpenAIJudge ──────────────────────────────────────────────────────────────


class TestOpenAIJudge:
    def test_defaults(self):
        judge = OpenAIJudge()
        assert judge.model == "gpt-4o"
        assert judge.temperature == 0.0
        assert judge.seed == 42

    def test_complete_sync_delegates_to_inner_llm(self, monkeypatch):
        judge = OpenAIJudge()
        fake = FakeSyncClient("delegated text")
        monkeypatch.setattr(judge._llm, "_get_sync_client", lambda: fake)
        assert judge.complete_sync("s", "u") == "delegated text"

    async def test_complete_async_delegates_to_inner_llm(self, monkeypatch):
        judge = OpenAIJudge()
        fake = FakeAsyncClient("delegated async")
        monkeypatch.setattr(judge._llm, "_get_async_client", lambda: fake)
        assert await judge.complete("s", "u") == "delegated async"

    def test_evaluate_sync_parses_json(self, monkeypatch):
        payload = {"score": 0.9, "reasoning": "good"}
        judge = OpenAIJudge()
        fake = FakeSyncClient(json.dumps(payload))
        monkeypatch.setattr(judge._llm, "_get_sync_client", lambda: fake)
        result = judge.evaluate_sync("s", "u")
        assert result == payload

    def test_evaluate_sync_uses_deterministic_sampling(self, monkeypatch):
        judge = OpenAIJudge(seed=123, temperature=0.0)
        fake = FakeSyncClient("{}")
        monkeypatch.setattr(judge._llm, "_get_sync_client", lambda: fake)
        judge.evaluate_sync("s", "u")
        call = fake.calls[0]
        assert call["seed"] == 123
        assert call["temperature"] == 0.0
        assert call["response_format"] == {"type": "json_object"}

    def test_evaluate_sync_empty_content_becomes_empty_dict(self, monkeypatch):
        judge = OpenAIJudge()
        fake = FakeSyncClient(None)
        monkeypatch.setattr(judge._llm, "_get_sync_client", lambda: fake)
        assert judge.evaluate_sync("s", "u") == {}

    async def test_evaluate_async_parses_json(self, monkeypatch):
        payload = {"rule_results": [], "overall_reasoning": "n/a"}
        judge = OpenAIJudge()
        fake = FakeAsyncClient(json.dumps(payload))
        monkeypatch.setattr(judge._llm, "_get_async_client", lambda: fake)
        result = await judge.evaluate("s", "u")
        assert result == payload
