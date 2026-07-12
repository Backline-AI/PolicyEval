"""Tests for the LLM judge implementations."""

from policyeval.judges.openai_judge import OpenAIJudge
from tests.conftest import MockJudge


class TestMockJudge:
    async def test_async_evaluate_returns_response(self):
        judge = MockJudge({"result": "ok"})
        result = await judge.evaluate("sys", "prompt")
        assert result == {"result": "ok"}

    def test_sync_evaluate_returns_response(self):
        judge = MockJudge({"result": "ok"})
        result = judge.evaluate_sync("sys", "prompt")
        assert result == {"result": "ok"}

    def test_calls_recorded(self):
        judge = MockJudge({})
        judge.evaluate_sync("sys1", "prompt1")
        judge.evaluate_sync("sys2", "prompt2")
        assert len(judge.calls) == 2
        assert judge.calls[0] == ("sys1", "prompt1")


class TestOpenAIJudgeInit:
    def test_default_params(self):
        judge = OpenAIJudge()
        assert judge.model == "gpt-4o"
        assert judge.temperature == 0.0
        assert judge.seed == 42

    def test_custom_params(self):
        judge = OpenAIJudge(model="gpt-3.5-turbo", temperature=0.5, seed=0)
        assert judge.model == "gpt-3.5-turbo"
        assert judge.temperature == 0.5
        assert judge.seed == 0

    def test_base_url_stored(self):
        judge = OpenAIJudge(base_url="http://localhost:8080")
        assert judge._base_url == "http://localhost:8080"
        assert judge._llm._base_url == "http://localhost:8080"

    def test_lazy_client_creation(self):
        judge = OpenAIJudge()
        assert judge._llm._async_client is None
        assert judge._llm._sync_client is None
