"""Core evaluation engine that orchestrates judge calls and metrics."""

from __future__ import annotations

import asyncio
from typing import Literal, Optional

from policyeval.judges.base import LLMJudge
from policyeval.metrics.adherence import (
    _batch_score_instruction,
    _format_rules_block,
    _score_instruction_for_rule,
    build_adherence_report,
)
from policyeval.metrics.compliance import maybe_compute_compliance
from policyeval.metrics.coverage import build_coverage_prompt, parse_coverage_response
from policyeval.policy.models import AdherenceType, Policy, Rule
from policyeval.reporting.models import (
    AdherenceReport,
    CoverageReport,
    PolicyReport,
    RuleResult,
)

_DEFAULT_SYSTEM_PROMPT = (
    "You are an impartial policy compliance evaluator. "
    "Evaluate the model output objectively and return only valid JSON."
)

# Reasoning attached to a rule the judge never returned a verdict for. When the
# judge response is parsed, any rule absent from it is back-filled with a fail
# score carrying this exact text — callers detect it to distinguish a real
# judge verdict from a missing one.
MISSING_RULE_REASONING = "Rule not evaluated by the judge (missing from response)."

EvalMode = Literal["batch", "sequential"]
MetricName = Literal["adherence", "coverage"]

_INPUT_SECTION = """
## Input (the original request or context)
{input}
"""

_CONTEXT_SECTION = """
## Context (additional context for reasoning about changes outside the policy)
{context}
"""

_BATCH_PROMPT_TEMPLATE = """\
You are evaluating a model output against a set of policy rules.
{input_section}
## Output (the model response to evaluate)
{output}
{context_section}
## Rules to evaluate
{rules_block}

For EACH rule, return:
- "rule_id": the rule's id
- "score": {score_instruction}
- "reasoning": a concise explanation (1-3 sentences) for this specific rule

Also return:
- "overall_reasoning": a short summary of the overall adherence assessment

Return a JSON object with this exact shape:
{{
  "rule_results": [
    {{"rule_id": "R1", "score": 0.0, "reasoning": "..."}},
    ...
  ],
  "overall_reasoning": "..."
}}
"""

_SEQUENTIAL_PROMPT_TEMPLATE = """\
You are evaluating a model output against a single policy rule.
{input_section}
## Output (the model response to evaluate)
{output}
{context_section}
## Rule
ID: {rule_id}
Description: {rule_description}{scope_line}

{score_instruction}

Return a JSON object with this exact shape:
{{
  "rule_id": "{rule_id}",
  "score": <number>,
  "reasoning": "..."
}}
"""


class EvaluationEngine:
    """Orchestrates adherence, coverage, and compliance evaluation.

    Args:
        judge: The :class:`~policyeval.judges.base.LLMJudge` to use for
            LLM-evaluated rules and coverage.
        system_prompt: System message that sets the judge's persona and
            domain context.
        eval_mode: ``"batch"`` (default) sends all LLM-evaluated rules in
            a single prompt; ``"sequential"`` sends one prompt per rule.
        adherence_weight: Weight for adherence in the compliance score.
        coverage_weight: Weight for coverage in the compliance score.
    """

    def __init__(
        self,
        judge: LLMJudge,
        system_prompt: Optional[str] = None,
        eval_mode: EvalMode = "batch",
        adherence_weight: float = 1.0,
        coverage_weight: float = 1.0,
    ) -> None:
        self.judge = judge
        self.system_prompt = system_prompt or _DEFAULT_SYSTEM_PROMPT
        self.eval_mode = eval_mode
        self.adherence_weight = adherence_weight
        self.coverage_weight = coverage_weight

    # ------------------------------------------------------------------
    # Public synchronous entry point
    # ------------------------------------------------------------------

    def evaluate(
        self,
        input_text: Optional[str],
        output_text: str,
        policy: Policy,
        context: Optional[str] = None,
        metrics: Optional[list[MetricName]] = None,
    ) -> PolicyReport:
        """Run evaluation synchronously.

        Args:
            input_text: The original prompt/context given to the model,
                or ``None`` to omit the input section from the judge prompt.
            output_text: The model's response to evaluate.
            policy: The :class:`~policyeval.policy.models.Policy` to evaluate against.
            context: Optional free-text context injected after the output
                section. Use this to explain changes that appear in the output
                but are not covered by any rule (e.g. transitive dependency
                upgrades). When ``None`` the context section is omitted.
            metrics: Which metrics to compute. Defaults to both
                ``["adherence", "coverage"]``. Pass ``["adherence"]`` or
                ``["coverage"]`` to run a single metric (saves LLM calls).

        Returns:
            A :class:`~policyeval.reporting.models.PolicyReport`.
        """
        metrics = _normalise_metrics(metrics)

        adherence: Optional[AdherenceReport] = None
        coverage: Optional[CoverageReport] = None

        if "adherence" in metrics:
            adherence = self._evaluate_adherence_sync(
                input_text, output_text, policy, context
            )

        if "coverage" in metrics:
            coverage = self._evaluate_coverage_sync(
                input_text, output_text, policy, context
            )

        compliance = maybe_compute_compliance(
            adherence.score if adherence else None,
            coverage.score if coverage else None,
            self.adherence_weight,
            self.coverage_weight,
        )

        reasoning = _build_overall_reasoning(adherence, coverage, compliance)

        return PolicyReport(
            adherence=adherence,
            coverage=coverage,
            compliance_score=compliance,
            reasoning=reasoning,
            metadata={
                "policy_name": policy.name,
                "policy_version": policy.version,
                "eval_mode": self.eval_mode,
                "metrics": list(metrics),
            },
        )

    # ------------------------------------------------------------------
    # Public async entry point
    # ------------------------------------------------------------------

    async def aevaluate(
        self,
        input_text: Optional[str],
        output_text: str,
        policy: Policy,
        context: Optional[str] = None,
        metrics: Optional[list[MetricName]] = None,
    ) -> PolicyReport:
        """Run evaluation asynchronously.

        When both metrics are requested they are executed concurrently.
        """
        metrics = _normalise_metrics(metrics)

        adherence: Optional[AdherenceReport] = None
        coverage: Optional[CoverageReport] = None

        run_adherence = "adherence" in metrics
        run_coverage = "coverage" in metrics

        if run_adherence and run_coverage:
            adherence, coverage = await asyncio.gather(
                self._evaluate_adherence_async(
                    input_text, output_text, policy, context
                ),
                self._evaluate_coverage_async(input_text, output_text, policy, context),
            )
        elif run_adherence:
            adherence = await self._evaluate_adherence_async(
                input_text, output_text, policy, context
            )
        elif run_coverage:
            coverage = await self._evaluate_coverage_async(
                input_text, output_text, policy, context
            )

        compliance = maybe_compute_compliance(
            adherence.score if adherence else None,
            coverage.score if coverage else None,
            self.adherence_weight,
            self.coverage_weight,
        )

        reasoning = _build_overall_reasoning(adherence, coverage, compliance)

        return PolicyReport(
            adherence=adherence,
            coverage=coverage,
            compliance_score=compliance,
            reasoning=reasoning,
            metadata={
                "policy_name": policy.name,
                "policy_version": policy.version,
                "eval_mode": self.eval_mode,
                "metrics": list(metrics),
            },
        )

    # ------------------------------------------------------------------
    # Adherence helpers
    # ------------------------------------------------------------------

    def _evaluate_adherence_sync(
        self,
        input_text: Optional[str],
        output_text: str,
        policy: Policy,
        context: Optional[str] = None,
    ) -> AdherenceReport:
        llm_rules = [r for r in policy.rules if r.evaluator is None]
        prog_rules = [r for r in policy.rules if r.evaluator is not None]

        rule_results: list[RuleResult] = []

        # Programmatic evaluators
        for rule in prog_rules:
            result = rule.evaluator(input_text, output_text, rule)  # type: ignore[misc]
            rule_results.append(result)

        # LLM evaluation
        if llm_rules:
            llm_results, overall_reasoning = self._llm_adherence_sync(
                input_text, output_text, llm_rules, context
            )
            rule_results.extend(llm_results)
        else:
            overall_reasoning = "All rules evaluated programmatically."

        # Preserve original policy rule ordering
        rule_results = _sort_by_policy_order(rule_results, policy)

        return build_adherence_report(rule_results, overall_reasoning)

    async def _evaluate_adherence_async(
        self,
        input_text: Optional[str],
        output_text: str,
        policy: Policy,
        context: Optional[str] = None,
    ) -> AdherenceReport:
        llm_rules = [r for r in policy.rules if r.evaluator is None]
        prog_rules = [r for r in policy.rules if r.evaluator is not None]

        rule_results: list[RuleResult] = []

        for rule in prog_rules:
            result = rule.evaluator(input_text, output_text, rule)  # type: ignore[misc]
            rule_results.append(result)

        if llm_rules:
            llm_results, overall_reasoning = await self._llm_adherence_async(
                input_text, output_text, llm_rules, context
            )
            rule_results.extend(llm_results)
        else:
            overall_reasoning = "All rules evaluated programmatically."

        rule_results = _sort_by_policy_order(rule_results, policy)
        return build_adherence_report(rule_results, overall_reasoning)

    def _llm_adherence_sync(
        self,
        input_text: Optional[str],
        output_text: str,
        rules: list[Rule],
        context: Optional[str] = None,
    ) -> tuple[list[RuleResult], str]:
        if self.eval_mode == "sequential":
            return self._sequential_adherence_sync(
                input_text, output_text, rules, context
            )
        return self._batch_adherence_sync(input_text, output_text, rules, context)

    async def _llm_adherence_async(
        self,
        input_text: Optional[str],
        output_text: str,
        rules: list[Rule],
        context: Optional[str] = None,
    ) -> tuple[list[RuleResult], str]:
        if self.eval_mode == "sequential":
            return await self._sequential_adherence_async(
                input_text, output_text, rules, context
            )
        return await self._batch_adherence_async(
            input_text, output_text, rules, context
        )

    def _batch_adherence_sync(
        self,
        input_text: Optional[str],
        output_text: str,
        rules: list[Rule],
        context: Optional[str] = None,
    ) -> tuple[list[RuleResult], str]:
        prompt = _build_batch_prompt(input_text, output_text, rules, context)
        raw = self.judge.evaluate_sync(self.system_prompt, prompt)
        return _parse_batch_response(raw, rules)

    async def _batch_adherence_async(
        self,
        input_text: Optional[str],
        output_text: str,
        rules: list[Rule],
        context: Optional[str] = None,
    ) -> tuple[list[RuleResult], str]:
        prompt = _build_batch_prompt(input_text, output_text, rules, context)
        raw = await self.judge.evaluate(self.system_prompt, prompt)
        return _parse_batch_response(raw, rules)

    def _sequential_adherence_sync(
        self,
        input_text: Optional[str],
        output_text: str,
        rules: list[Rule],
        context: Optional[str] = None,
    ) -> tuple[list[RuleResult], str]:
        results: list[RuleResult] = []
        for rule in rules:
            prompt = _build_sequential_prompt(input_text, output_text, rule, context)
            raw = self.judge.evaluate_sync(self.system_prompt, prompt)
            results.append(_parse_sequential_response(raw, rule))
        overall_reasoning = _aggregate_reasoning(results)
        return results, overall_reasoning

    async def _sequential_adherence_async(
        self,
        input_text: Optional[str],
        output_text: str,
        rules: list[Rule],
        context: Optional[str] = None,
    ) -> tuple[list[RuleResult], str]:
        tasks = [
            self.judge.evaluate(
                self.system_prompt,
                _build_sequential_prompt(input_text, output_text, r, context),
            )
            for r in rules
        ]
        responses = await asyncio.gather(*tasks)
        results = [
            _parse_sequential_response(raw, rule) for raw, rule in zip(responses, rules)
        ]
        overall_reasoning = _aggregate_reasoning(results)
        return results, overall_reasoning

    # ------------------------------------------------------------------
    # Coverage helpers
    # ------------------------------------------------------------------

    def _evaluate_coverage_sync(
        self,
        input_text: Optional[str],
        output_text: str,
        policy: Policy,
        context: Optional[str] = None,
    ) -> CoverageReport:
        prompt = build_coverage_prompt(input_text, output_text, policy, context)
        raw = self.judge.evaluate_sync(self.system_prompt, prompt)
        return parse_coverage_response(raw)

    async def _evaluate_coverage_async(
        self,
        input_text: Optional[str],
        output_text: str,
        policy: Policy,
        context: Optional[str] = None,
    ) -> CoverageReport:
        prompt = build_coverage_prompt(input_text, output_text, policy, context)
        raw = await self.judge.evaluate(self.system_prompt, prompt)
        return parse_coverage_response(raw)


# ------------------------------------------------------------------
# Prompt helpers
# ------------------------------------------------------------------


def _build_input_section(input_text: Optional[str]) -> str:
    """Return the ``## Input`` section, or an empty string when *input_text* is ``None``."""
    if input_text is None:
        return ""
    return _INPUT_SECTION.format(input=input_text)


def _build_context_section(context: Optional[str]) -> str:
    """Return the ``## Context`` section, or an empty string when *context* is ``None``."""
    if not context:
        return ""
    return _CONTEXT_SECTION.format(context=context)


def _build_batch_prompt(
    input_text: Optional[str],
    output_text: str,
    rules: list[Rule],
    context: Optional[str] = None,
) -> str:
    return _BATCH_PROMPT_TEMPLATE.format(
        input_section=_build_input_section(input_text),
        output=output_text,
        context_section=_build_context_section(context),
        rules_block=_format_rules_block(rules),
        score_instruction=_batch_score_instruction(rules),
    )


def _build_sequential_prompt(
    input_text: Optional[str],
    output_text: str,
    rule: Rule,
    context: Optional[str] = None,
) -> str:
    scope_line = f"\nScope: {rule.scope}" if rule.scope else ""
    return _SEQUENTIAL_PROMPT_TEMPLATE.format(
        input_section=_build_input_section(input_text),
        output=output_text,
        context_section=_build_context_section(context),
        rule_id=rule.id,
        rule_description=rule.description,
        scope_line=scope_line,
        score_instruction=_score_instruction_for_rule(rule),
    )


def _normalize_rule_id(rule_id: str) -> str:
    return rule_id.strip().lower()


def _rule_id_path(rule_id: str) -> str:
    """The package-path portion of a ``path@version`` rule id."""
    return rule_id.split("@", 1)[0].strip().lower()


def _match_rule(
    response_id: str, rules: list[Rule], consumed: set[str]
) -> Optional[Rule]:
    """Best-effort match of a judge-returned ``rule_id`` to a policy Rule.

    The judge often echoes a ``rule_id`` that is not byte-for-byte identical to
    the one we sent — it drops the ``@version`` suffix, echoes the *target*
    version instead of the current one, changes case, or follows the prompt's
    ``"R1"`` example. Exact matching alone silently discards these items and the
    rule is then back-filled as a failure, producing false negatives. We fall
    back through progressively looser matches, each requiring a *unique*
    unconsumed candidate so an ambiguous echo is never guessed at.
    """
    available = [r for r in rules if r.id not in consumed]

    for rule in available:
        if rule.id == response_id:
            return rule

    norm = _normalize_rule_id(response_id)
    norm_matches = [r for r in available if _normalize_rule_id(r.id) == norm]
    if len(norm_matches) == 1:
        return norm_matches[0]

    resp_path = _rule_id_path(response_id)
    if resp_path:
        path_matches = [r for r in available if _rule_id_path(r.id) == resp_path]
        if len(path_matches) == 1:
            return path_matches[0]

    return None


def _parse_batch_response(raw: dict, rules: list[Rule]) -> tuple[list[RuleResult], str]:
    overall_reasoning = str(raw.get("overall_reasoning", ""))
    results: list[RuleResult] = []
    consumed: set[str] = set()

    for item in raw.get("rule_results", []):
        response_id = str(item.get("rule_id", ""))
        rule = _match_rule(response_id, rules, consumed)
        if rule is None:
            continue
        consumed.add(rule.id)
        raw_score = float(item.get("score", 0.0))
        score = _clamp_score(raw_score, rule)
        results.append(
            RuleResult(
                # Store the canonical rule id, not the (possibly fuzzy) echo, so
                # downstream lookups keyed on the policy rule id still resolve.
                rule_id=rule.id,
                score=score,
                adherence_type=rule.adherence_type,
                severity=rule.severity,
                reasoning=str(item.get("reasoning", "")),
                source="llm",
            )
        )

    # Fill in missing rules with a fail score
    present_ids = {r.rule_id for r in results}
    for rule in rules:
        if rule.id not in present_ids:
            results.append(
                RuleResult(
                    rule_id=rule.id,
                    score=0.0,
                    adherence_type=rule.adherence_type,
                    severity=rule.severity,
                    reasoning=MISSING_RULE_REASONING,
                    source="llm",
                )
            )

    return results, overall_reasoning


def _parse_sequential_response(raw: dict, rule: Rule) -> RuleResult:
    raw_score = float(raw.get("score", 0.0))
    score = _clamp_score(raw_score, rule)
    return RuleResult(
        rule_id=rule.id,
        score=score,
        adherence_type=rule.adherence_type,
        severity=rule.severity,
        reasoning=str(raw.get("reasoning", "")),
        source="llm",
    )


def _clamp_score(score: float, rule: Rule) -> float:
    if rule.adherence_type == AdherenceType.binary:
        return 1.0 if score >= 0.5 else 0.0
    return max(0.0, min(1.0, score))


def _sort_by_policy_order(
    results: list[RuleResult], policy: Policy
) -> list[RuleResult]:
    order = {rule.id: i for i, rule in enumerate(policy.rules)}
    return sorted(results, key=lambda r: order.get(r.rule_id, 9999))


def _aggregate_reasoning(results: list[RuleResult]) -> str:
    passed = sum(1 for r in results if r.passed)
    total = len(results)
    return (
        f"{passed}/{total} rules passed. "
        + "; ".join(f"{r.rule_id}: {r.reasoning[:80]}" for r in results if not r.passed)
    ).strip()


def _normalise_metrics(metrics: Optional[list[str]]) -> set[str]:
    if metrics is None:
        return {"adherence", "coverage"}
    valid = {"adherence", "coverage"}
    normalised = {m.lower() for m in metrics} & valid
    if not normalised:
        raise ValueError(
            f"metrics must include at least one of {valid}. Got: {metrics}"
        )
    return normalised


def _build_overall_reasoning(
    adherence: Optional[AdherenceReport],
    coverage: Optional[CoverageReport],
    compliance: Optional[float],
) -> str:
    parts = []
    if adherence is not None:
        parts.append(f"Adherence: {adherence.score:.2f} – {adherence.reasoning}")
    if coverage is not None:
        parts.append(f"Coverage: {coverage.score:.2f} – {coverage.reasoning}")
    if compliance is not None:
        parts.append(f"Compliance: {compliance:.2f}")
    return " | ".join(parts)
