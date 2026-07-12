"""Reporting domain models: RuleResult, UncoveredAction, and metric reports."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field, computed_field, model_validator

from policyeval.policy.models import AdherenceType


class MetricReport(BaseModel):
    """Base class for all metric reports.

    Every metric report carries a numeric ``score`` in [0, 1] and a
    ``reasoning`` string that explains the score.  Subclasses add
    domain-specific detail fields.
    """

    score: float = Field(ge=0.0, le=1.0)
    reasoning: str


class RuleResult(BaseModel):
    """Evaluation outcome for a single policy rule.

    Attributes:
        rule_id: Matches the ``id`` of the source :class:`~policyeval.policy.models.Rule`.
        score: For ``binary`` rules: 0.0 or 1.0. For ``float`` rules: 0–1.
        adherence_type: Copied from the source rule.
        severity: Copied from the source rule (user-provided weight).
        reasoning: Judge's or evaluator's explanation for this specific rule.
        source: ``"llm"`` if evaluated by the LLM judge, ``"programmatic"``
            if evaluated by a custom callable attached to the rule.
    """

    rule_id: str
    score: float = Field(ge=0.0, le=1.0)
    adherence_type: AdherenceType
    severity: float = Field(ge=0.0, le=1.0)
    reasoning: str
    source: str = "llm"

    @computed_field  # type: ignore[misc]
    @property
    def passed(self) -> bool:
        """True when the rule is considered satisfied.

        For ``binary`` rules: score must equal 1.0 exactly.
        For ``float`` rules: score must be >= 0.5.
        """
        if self.adherence_type == AdherenceType.binary:
            return self.score == 1.0
        return self.score >= 0.5


class UncoveredAction(BaseModel):
    """An action or change found in the output that has no corresponding rule.

    These represent *unexpected* behavior – the output did something that
    no rule in the policy addresses.

    Attributes:
        description: What the unexpected action/change is.
        severity: LLM-determined severity (0–1) of this uncovered action.
        reasoning: Why this action is not covered by any policy rule.
    """

    description: str
    severity: float = Field(ge=0.0, le=1.0)
    reasoning: str


class AdherenceReport(MetricReport):
    """Adherence metric report.

    Attributes:
        score: Weighted adherence score across all rules. Computed
            deterministically from per-rule scores and severities.
            Floored to 0 if any ``binary`` rule fails.
        reasoning: Overall adherence explanation from the judge.
        rule_results: Per-rule evaluation outcomes.
        violations: Computed property – rules that did not pass.
    """

    rule_results: list[RuleResult] = Field(default_factory=list)

    @computed_field  # type: ignore[misc]
    @property
    def violations(self) -> list[RuleResult]:
        """Rules that did not pass."""
        return [r for r in self.rule_results if not r.passed]


class CoverageReport(MetricReport):
    """Coverage metric report.

    Attributes:
        score: 1.0 = all output actions are covered by policy rules;
            0.0 = the output is dominated by unplanned actions.
        reasoning: Overall coverage explanation from the judge.
        uncovered_actions: Actions/changes in the output not addressed
            by any rule, each with an LLM-determined severity and reasoning.
    """

    uncovered_actions: list[UncoveredAction] = Field(default_factory=list)


class PolicyReport(BaseModel):
    """Top-level evaluation report composing adherence, coverage, and compliance.

    ``adherence`` and ``coverage`` are ``Optional`` – either can be ``None``
    when only one metric was requested.  ``compliance_score`` is ``None``
    unless both sub-reports are present.

    Attributes:
        adherence: Adherence sub-report (``None`` if coverage-only).
        coverage: Coverage sub-report (``None`` if adherence-only).
        compliance_score: Weighted harmonic mean of adherence and coverage
            scores (falls back to arithmetic mean when either is 0). ``None``
            when only one metric was evaluated.
        reasoning: Overall summary combining both dimensions.
        evaluated_at: UTC timestamp of when the evaluation completed.
        metadata: Arbitrary key-value pairs for tracing (model, policy name, …).
    """

    adherence: Optional[AdherenceReport] = None
    coverage: Optional[CoverageReport] = None
    compliance_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    reasoning: str = ""
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_consistency(self) -> "PolicyReport":
        if self.adherence is None and self.coverage is None:
            raise ValueError("At least one of adherence or coverage must be set")
        return self

    def passed(
        self,
        min_adherence: Optional[float] = None,
        min_coverage: Optional[float] = None,
        min_compliance: Optional[float] = None,
    ) -> bool:
        """Check whether this report meets the given thresholds.

        Args:
            min_adherence: Minimum required adherence score (0–1).
            min_coverage: Minimum required coverage score (0–1).
            min_compliance: Minimum required compliance score (0–1).

        Returns:
            ``True`` if all supplied thresholds are met.
        """
        if min_adherence is not None:
            if self.adherence is None or self.adherence.score < min_adherence:
                return False
        if min_coverage is not None:
            if self.coverage is None or self.coverage.score < min_coverage:
                return False
        if min_compliance is not None:
            if self.compliance_score is None or self.compliance_score < min_compliance:
                return False
        return True


class ExecutionResult(BaseModel):
    """Result of a policy-guided generation.

    Produced by :class:`~policyeval.testing.executor.PolicyExecutor`.
    Contains only the generated output – evaluation is a separate,
    explicit step via :class:`~policyeval.testing.test_case.PolicyTest`.

    Attributes:
        output: The generated text that was produced in compliance with
            the policy rules.
        policy_name: Name of the policy used during generation.
        generated_at: UTC timestamp of when generation completed.
        metadata: Arbitrary key-value pairs for tracing (model, policy
            version, …).
    """

    output: str
    policy_name: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict = Field(default_factory=dict)
