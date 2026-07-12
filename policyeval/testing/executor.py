"""PolicyExecutor: the primary user-facing API for policy-guided generation."""

from __future__ import annotations

from typing import Optional

from policyeval.engine.executor import ExecutionEngine
from policyeval.llm.base import LLM
from policyeval.llm.openai import OpenAILLM
from policyeval.policy.models import Policy
from policyeval.reporting.models import ExecutionResult


class PolicyExecutor:
    """Generate a policy-compliant LLM response for a given input.

    This is the primary user-facing API for policy execution.  It wraps
    :class:`~policyeval.engine.executor.ExecutionEngine` and wires in a
    default :class:`~policyeval.llm.openai.OpenAILLM` if no custom LLM is
    provided.

    Generation and evaluation are **separate operations**.  After calling
    :meth:`run`, pass ``result.output`` to
    :class:`~policyeval.testing.test_case.PolicyTest` to evaluate it.

    Args:
        policy: The :class:`~policyeval.policy.models.Policy` whose rules
            are encoded as generation constraints.
        input: The user query or context to respond to.
        llm: The :class:`~policyeval.llm.base.LLM` to use for generation.
            Defaults to :class:`~policyeval.llm.openai.OpenAILLM` with
            ``gpt-4o``.  Pass any OpenAI-compatible LLM (including a
            LiteLLM proxy) here.
        system_prompt: Optional persona / domain context override.

    Examples::

        from policyeval import Policy, Rule, PolicyExecutor, PolicyTest

        policy = Policy(
            name="Financial Advice Safety",
            rules=[
                Rule(id="R1", description="Must not provide personalized investment advice",
                     severity=1.0, adherence_type="binary"),
                Rule(id="R2", description="Should include a risk disclaimer",
                     severity=0.7, adherence_type="float"),
            ],
        )

        # 1. Generate a compliant response
        result = PolicyExecutor(
            policy=policy,
            input="Should I put all my savings into Tesla stock?",
        ).run()
        print(result.output)

        # 2. Evaluate separately (explicit, no hidden logic)
        report = PolicyTest(
            input="Should I put all my savings into Tesla stock?",
            output=result.output,
            policy=policy,
        ).run()
        print(f"Compliance: {report.compliance_score:.2f}")

        # 3. Compose a retry loop yourself
        for attempt in range(3):
            result = PolicyExecutor(policy=policy, input=query).run()
            report = PolicyTest(input=query, output=result.output, policy=policy).run()
            if report.compliance_score >= 0.9:
                break

        # 4. Use LiteLLM for a different provider
        from policyeval.llm import OpenAILLM
        llm = OpenAILLM(model="anthropic/claude-3-opus", base_url="http://localhost:4000")
        result = PolicyExecutor(policy=policy, input="...", llm=llm).run()
    """

    def __init__(
        self,
        *,
        policy: Policy,
        input: str,
        llm: Optional[LLM] = None,
        system_prompt: Optional[str] = None,
    ) -> None:
        self.policy = policy
        self.input = input
        self.llm = llm or OpenAILLM()
        self.system_prompt = system_prompt

    def _make_engine(self) -> ExecutionEngine:
        return ExecutionEngine(llm=self.llm, system_prompt=self.system_prompt)

    def run(self) -> ExecutionResult:
        """Generate a compliant response synchronously.

        Returns:
            An :class:`~policyeval.reporting.models.ExecutionResult`
            containing the generated ``output``.
        """
        engine = self._make_engine()
        return engine.execute_sync(self.input, self.policy)

    async def arun(self) -> ExecutionResult:
        """Generate a compliant response asynchronously.

        Returns:
            An :class:`~policyeval.reporting.models.ExecutionResult`
            containing the generated ``output``.
        """
        engine = self._make_engine()
        return await engine.execute(self.input, self.policy)
