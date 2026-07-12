"""Tests for policy-guided generation (ExecutionEngine and PolicyExecutor)."""

from __future__ import annotations

from policyeval.engine.executor import (
    ExecutionEngine,
    _build_execution_prompt,
    _format_rules_block,
)
from policyeval.policy.models import Policy, Rule
from policyeval.reporting.models import ExecutionResult
from policyeval.testing.executor import PolicyExecutor
from tests.conftest import MockJudge


POLICY = Policy(
    name="Financial Advice Safety",
    version="1.0",
    rules=[
        Rule(
            id="no_advice",
            description="Must not provide personalized investment advice",
            severity=1.0,
            adherence_type="binary",
        ),
        Rule(
            id="disclaimer",
            description="Should include a risk disclaimer",
            severity=0.7,
            adherence_type="float",
            scope="investment queries",
        ),
    ],
)


class EchoLLM(MockJudge):
    """A mock LLM that records prompts and returns a fixed string."""

    def __init__(self, output: str = "Generated response") -> None:
        super().__init__({})
        self._output = output

    async def complete(self, system_prompt: str, prompt: str) -> str:
        self.calls.append((system_prompt, prompt))
        return self._output

    def complete_sync(self, system_prompt: str, prompt: str) -> str:
        self.calls.append((system_prompt, prompt))
        return self._output


# ── Prompt-building helpers ────────────────────────────────────────────────


class TestPromptBuilding:
    def test_format_rules_block_marks_binary_mandatory(self):
        block = _format_rules_block(POLICY)
        assert "[MANDATORY]" in block
        assert "no_advice" in block

    def test_format_rules_block_shows_severity_for_float(self):
        block = _format_rules_block(POLICY)
        assert "severity: 0.7" in block

    def test_format_rules_block_includes_scope(self):
        block = _format_rules_block(POLICY)
        assert "scope: investment queries" in block

    def test_build_execution_prompt_includes_input_and_rules(self):
        prompt = _build_execution_prompt("Should I buy Tesla?", POLICY)
        assert "Should I buy Tesla?" in prompt
        assert "Policy Rules" in prompt
        assert "no_advice" in prompt


# ── ExecutionEngine ─────────────────────────────────────────────────────────


class TestExecutionEngine:
    def test_execute_sync_returns_result(self):
        llm = EchoLLM("Consult a licensed advisor.")
        engine = ExecutionEngine(llm=llm)
        result = engine.execute_sync("Should I buy Tesla?", POLICY)
        assert isinstance(result, ExecutionResult)
        assert result.output == "Consult a licensed advisor."
        assert result.policy_name == "Financial Advice Safety"
        assert result.metadata["policy_version"] == "1.0"

    def test_execute_sync_passes_rules_to_llm(self):
        llm = EchoLLM()
        ExecutionEngine(llm=llm).execute_sync("input text", POLICY)
        system_prompt, user_prompt = llm.calls[0]
        assert "no_advice" in user_prompt
        assert "input text" in user_prompt

    def test_default_system_prompt_used(self):
        llm = EchoLLM()
        ExecutionEngine(llm=llm).execute_sync("q", POLICY)
        system_prompt, _ = llm.calls[0]
        assert "policy rules" in system_prompt.lower()

    def test_custom_system_prompt_overrides_default(self):
        llm = EchoLLM()
        ExecutionEngine(llm=llm, system_prompt="You are a bank teller.").execute_sync(
            "q", POLICY
        )
        system_prompt, _ = llm.calls[0]
        assert system_prompt == "You are a bank teller."

    async def test_execute_async_returns_result(self):
        llm = EchoLLM("async output")
        engine = ExecutionEngine(llm=llm)
        result = await engine.execute("Should I buy Tesla?", POLICY)
        assert result.output == "async output"
        assert result.policy_name == "Financial Advice Safety"


# ── PolicyExecutor (public API) ──────────────────────────────────────────────


class TestPolicyExecutor:
    def test_run_uses_provided_llm(self):
        llm = EchoLLM("compliant text")
        result = PolicyExecutor(policy=POLICY, input="q", llm=llm).run()
        assert result.output == "compliant text"

    def test_run_passes_system_prompt(self):
        llm = EchoLLM()
        PolicyExecutor(policy=POLICY, input="q", llm=llm, system_prompt="Persona").run()
        system_prompt, _ = llm.calls[0]
        assert system_prompt == "Persona"

    async def test_arun_uses_provided_llm(self):
        llm = EchoLLM("async compliant")
        result = await PolicyExecutor(policy=POLICY, input="q", llm=llm).arun()
        assert result.output == "async compliant"

    def test_defaults_to_openai_llm_when_none(self):
        executor = PolicyExecutor(policy=POLICY, input="q")
        # Should construct without error and lazily hold an OpenAILLM.
        from policyeval.llm.openai import OpenAILLM

        assert isinstance(executor.llm, OpenAILLM)
