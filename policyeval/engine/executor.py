"""Core execution engine for policy-guided LLM generation."""

from __future__ import annotations

from typing import Optional

from policyeval.llm.base import LLM
from policyeval.policy.models import AdherenceType, Policy
from policyeval.reporting.models import ExecutionResult

_DEFAULT_SYSTEM_PROMPT = (
    "You are a helpful assistant that strictly follows a set of policy rules. "
    "Respond to the user's request while adhering to every rule listed. "
    "Do not produce any output that goes beyond what the rules permit."
)

_RULES_BLOCK_TEMPLATE = """\
## Policy Rules
{rules}

"""

_EXECUTION_PROMPT_TEMPLATE = """\
{rules_block}## User Request
{input}

Respond to the user request above while strictly adhering to ALL policy rules listed.
Do not take any action or produce any content that is not covered by the rules."""


def _format_rules_block(policy: Policy) -> str:
    lines = []
    for rule in policy.rules:
        constraint_type = (
            "[MANDATORY]"
            if rule.adherence_type == AdherenceType.binary
            else f"[severity: {rule.severity:.1f}]"
        )
        scope_suffix = f" (scope: {rule.scope})" if rule.scope else ""
        lines.append(f"- {rule.id}: {rule.description} {constraint_type}{scope_suffix}")
    return _RULES_BLOCK_TEMPLATE.format(rules="\n".join(lines))


def _build_execution_prompt(input_text: str, policy: Policy) -> str:
    return _EXECUTION_PROMPT_TEMPLATE.format(
        rules_block=_format_rules_block(policy),
        input=input_text,
    )


class ExecutionEngine:
    """Generates a policy-compliant LLM response for a given input.

    This engine does one thing: builds a generation prompt that encodes
    the policy rules as constraints, calls :meth:`~policyeval.llm.base.LLM.complete`
    on the provided LLM, and returns the result.

    Evaluation is intentionally separate – pair with
    :class:`~policyeval.engine.evaluator.EvaluationEngine` or
    :class:`~policyeval.testing.test_case.PolicyTest` for that.

    Args:
        llm: The :class:`~policyeval.llm.base.LLM` used for generation.
            Any :class:`~policyeval.judges.base.LLMJudge` works here too.
        system_prompt: Optional persona / context override.  Defaults to
            a neutral policy-following assistant persona.
    """

    def __init__(
        self,
        llm: LLM,
        system_prompt: Optional[str] = None,
    ) -> None:
        self.llm = llm
        self.system_prompt = system_prompt or _DEFAULT_SYSTEM_PROMPT

    # ------------------------------------------------------------------
    # Public synchronous entry point
    # ------------------------------------------------------------------

    def execute_sync(self, input_text: str, policy: Policy) -> ExecutionResult:
        """Generate a policy-compliant response synchronously.

        Args:
            input_text: The user's query or context.
            policy: The :class:`~policyeval.policy.models.Policy` whose
                rules are encoded as generation constraints.

        Returns:
            An :class:`~policyeval.reporting.models.ExecutionResult` with
            the generated ``output``.
        """
        prompt = _build_execution_prompt(input_text, policy)
        output = self.llm.complete_sync(self.system_prompt, prompt)
        return ExecutionResult(
            output=output,
            policy_name=policy.name,
            metadata={"policy_version": policy.version},
        )

    # ------------------------------------------------------------------
    # Public async entry point
    # ------------------------------------------------------------------

    async def execute(self, input_text: str, policy: Policy) -> ExecutionResult:
        """Generate a policy-compliant response asynchronously.

        Args:
            input_text: The user's query or context.
            policy: The :class:`~policyeval.policy.models.Policy` whose
                rules are encoded as generation constraints.

        Returns:
            An :class:`~policyeval.reporting.models.ExecutionResult` with
            the generated ``output``.
        """
        prompt = _build_execution_prompt(input_text, policy)
        output = await self.llm.complete(self.system_prompt, prompt)
        return ExecutionResult(
            output=output,
            policy_name=policy.name,
            metadata={"policy_version": policy.version},
        )
