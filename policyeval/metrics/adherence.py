"""Adherence metric: compute a weighted score across rule results."""

from __future__ import annotations

from policyeval.policy.models import AdherenceType, Rule
from policyeval.reporting.models import AdherenceReport, RuleResult


def _format_rules_block(rules: list[Rule]) -> str:
    lines = []
    for rule in rules:
        scope_suffix = f" [scope: {rule.scope}]" if rule.scope else ""
        score_hint = (
            "binary (0 or 1)"
            if rule.adherence_type == AdherenceType.binary
            else "float (0.0–1.0)"
        )
        lines.append(
            f"- id: {rule.id} | type: {score_hint} | description: {rule.description}{scope_suffix}"
        )
    return "\n".join(lines)


def _score_instruction_for_rule(rule: Rule) -> str:
    if rule.adherence_type == AdherenceType.binary:
        return "1.0 if the rule is fully satisfied, 0.0 if it is violated (no intermediate values)"
    return "a float between 0.0 (completely violated) and 1.0 (fully satisfied)"


def _batch_score_instruction(rules: list[Rule]) -> str:
    has_binary = any(r.adherence_type == AdherenceType.binary for r in rules)
    has_float = any(r.adherence_type == AdherenceType.float for r in rules)
    if has_binary and has_float:
        return (
            "for binary rules: 1.0 or 0.0 only; "
            "for float rules: a continuous value between 0.0 and 1.0"
        )
    if has_binary:
        return "1.0 if the rule is fully satisfied, 0.0 if violated (no intermediate values)"
    return "a continuous float between 0.0 (fully violated) and 1.0 (fully satisfied)"


def compute_adherence_score(rule_results: list[RuleResult]) -> float:
    """Compute the weighted adherence score from a list of rule results.

    Formula::

        score = sum(r.score * r.severity for r in results) / sum(r.severity for r in results)

    If any ``binary`` rule has score ``0.0``, the entire score is floored to
    ``0.0`` (fail-fast semantics).

    Args:
        rule_results: Per-rule evaluation outcomes.

    Returns:
        A float in ``[0, 1]``.
    """
    if not rule_results:
        return 0.0

    for r in rule_results:
        if r.adherence_type == AdherenceType.binary and r.score == 0.0:
            return 0.0

    total_severity = sum(r.severity for r in rule_results)
    if total_severity == 0.0:
        return 0.0

    weighted_sum = sum(r.score * r.severity for r in rule_results)
    return weighted_sum / total_severity


def build_adherence_report(
    rule_results: list[RuleResult],
    overall_reasoning: str,
) -> AdherenceReport:
    """Construct an :class:`AdherenceReport` from pre-computed rule results.

    Args:
        rule_results: Ordered list of per-rule evaluation outcomes.
        overall_reasoning: Summary explanation from the judge.

    Returns:
        A validated :class:`AdherenceReport`.
    """
    score = compute_adherence_score(rule_results)
    return AdherenceReport(
        score=score,
        reasoning=overall_reasoning,
        rule_results=rule_results,
    )
