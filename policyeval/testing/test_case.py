"""PolicyTest: the primary user-facing API for running policy evaluations."""

from __future__ import annotations

from typing import Optional

from policyeval.engine.evaluator import EvalMode, EvaluationEngine, MetricName
from policyeval.judges.base import LLMJudge
from policyeval.judges.openai_judge import OpenAIJudge
from policyeval.policy.models import Policy
from policyeval.reporting.models import PolicyReport


class PolicyTest:
    """Run a policy evaluation against an (input, output) pair.

    This is the primary user-facing API.  It wraps the
    :class:`~policyeval.engine.evaluator.EvaluationEngine` and wires in
    a default :class:`~policyeval.judges.openai_judge.OpenAIJudge` if no
    custom judge is provided.

    Args:
        output: The model's response to evaluate.
        policy: The :class:`~policyeval.policy.models.Policy` to evaluate against.
        input: Optional original prompt / context given to the model under
            test. When ``None`` the ``## Input`` section is omitted from
            the judge prompt.
        context: Optional free-text context injected into the judge prompt
            after the output, before the rules. Use this to explain changes
            that appear in the output but are not described by any rule (e.g.
            transitive package upgrades pulled in by a direct dependency
            upgrade). When ``None`` the ``## Context`` section is omitted.
        judge: LLM judge to use. Defaults to
            :class:`~policyeval.judges.openai_judge.OpenAIJudge` with
            ``gpt-4o``.
        system_prompt: Optional persona / domain context for the judge
            (e.g. ``"You are a security expert..."``).
        eval_mode: ``"batch"`` (default) or ``"sequential"``.
        adherence_weight: Weight for adherence when computing the compliance
            score (default 1.0).
        coverage_weight: Weight for coverage when computing the compliance
            score (default 1.0).

    Example::

        from policyeval import Policy, Rule, PolicyTest

        policy = Policy(
            name="Financial Advice Safety",
            rules=[
                Rule(id="R1", description="Must not provide personalised investment advice",
                     severity=1.0, adherence_type="binary"),
            ],
        )

        test = PolicyTest(
            input="Should I buy Tesla stock?",
            output="I cannot provide personalised investment advice.",
            policy=policy,
            system_prompt="You are a financial compliance officer.",
        )

        report = test.run()
        print(report.compliance_score)
    """

    def __init__(
        self,
        *,
        output: str,
        policy: Policy,
        input: Optional[str] = None,
        context: Optional[str] = None,
        judge: Optional[LLMJudge] = None,
        system_prompt: Optional[str] = None,
        eval_mode: EvalMode = "batch",
        adherence_weight: float = 1.0,
        coverage_weight: float = 1.0,
    ) -> None:
        self.input = input
        self.context = context
        self.output = output
        self.policy = policy
        self.judge = judge or OpenAIJudge()
        self.system_prompt = system_prompt
        self.eval_mode = eval_mode
        self.adherence_weight = adherence_weight
        self.coverage_weight = coverage_weight

    def _make_engine(self) -> EvaluationEngine:
        return EvaluationEngine(
            judge=self.judge,
            system_prompt=self.system_prompt,
            eval_mode=self.eval_mode,
            adherence_weight=self.adherence_weight,
            coverage_weight=self.coverage_weight,
        )

    def run(
        self,
        metrics: Optional[list[MetricName]] = None,
    ) -> PolicyReport:
        """Run the evaluation synchronously.

        Args:
            metrics: Which metrics to compute. Defaults to
                ``["adherence", "coverage"]`` (both). Pass
                ``["adherence"]`` or ``["coverage"]`` to run only one,
                which saves an LLM call.

        Returns:
            A :class:`~policyeval.reporting.models.PolicyReport`.
        """
        engine = self._make_engine()
        return engine.evaluate(
            self.input,
            self.output,
            self.policy,
            context=self.context,
            metrics=metrics,
        )

    async def arun(
        self,
        metrics: Optional[list[MetricName]] = None,
    ) -> PolicyReport:
        """Run the evaluation asynchronously.

        When both adherence and coverage are requested they are evaluated
        concurrently, reducing wall-clock time.

        Args:
            metrics: Same as :meth:`run`.

        Returns:
            A :class:`~policyeval.reporting.models.PolicyReport`.
        """
        engine = self._make_engine()
        return await engine.aevaluate(
            self.input,
            self.output,
            self.policy,
            context=self.context,
            metrics=metrics,
        )
