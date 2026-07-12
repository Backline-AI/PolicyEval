"""Tests for reporting models."""

import pytest
from pydantic import ValidationError

from policyeval.policy.models import AdherenceType
from policyeval.reporting.models import (
    AdherenceReport,
    CoverageReport,
    PolicyReport,
    RuleResult,
    UncoveredAction,
)


class TestRuleResult:
    def test_binary_passed_when_score_one(self):
        r = RuleResult(
            rule_id="R1",
            score=1.0,
            adherence_type=AdherenceType.binary,
            severity=1.0,
            reasoning="Passed",
        )
        assert r.passed is True

    def test_binary_failed_when_score_zero(self):
        r = RuleResult(
            rule_id="R1",
            score=0.0,
            adherence_type=AdherenceType.binary,
            severity=1.0,
            reasoning="Failed",
        )
        assert r.passed is False

    def test_float_passed_at_threshold(self):
        r = RuleResult(
            rule_id="R1",
            score=0.5,
            adherence_type=AdherenceType.float,
            severity=0.5,
            reasoning="Threshold",
        )
        assert r.passed is True

    def test_float_failed_below_threshold(self):
        r = RuleResult(
            rule_id="R1",
            score=0.4,
            adherence_type=AdherenceType.float,
            severity=0.5,
            reasoning="Below threshold",
        )
        assert r.passed is False

    def test_source_default(self):
        r = RuleResult(
            rule_id="R1",
            score=1.0,
            adherence_type=AdherenceType.binary,
            severity=1.0,
            reasoning="ok",
        )
        assert r.source == "llm"


class TestAdherenceReport:
    def test_violations_computed(self):
        results = [
            RuleResult(
                rule_id="R1",
                score=1.0,
                adherence_type=AdherenceType.binary,
                severity=1.0,
                reasoning="ok",
            ),
            RuleResult(
                rule_id="R2",
                score=0.0,
                adherence_type=AdherenceType.binary,
                severity=0.5,
                reasoning="fail",
            ),
        ]
        report = AdherenceReport(score=0.5, reasoning="Mixed", rule_results=results)
        assert len(report.violations) == 1
        assert report.violations[0].rule_id == "R2"

    def test_no_violations(self):
        results = [
            RuleResult(
                rule_id="R1",
                score=1.0,
                adherence_type=AdherenceType.binary,
                severity=1.0,
                reasoning="ok",
            ),
        ]
        report = AdherenceReport(score=1.0, reasoning="All pass", rule_results=results)
        assert report.violations == []


class TestCoverageReport:
    def test_with_uncovered_actions(self):
        report = CoverageReport(
            score=0.6,
            reasoning="Some uncovered actions",
            uncovered_actions=[
                UncoveredAction(
                    description="Modified logging",
                    severity=0.3,
                    reasoning="No rule covers it",
                )
            ],
        )
        assert len(report.uncovered_actions) == 1
        assert report.uncovered_actions[0].severity == 0.3


class TestPolicyReport:
    def test_requires_at_least_one_metric(self):
        with pytest.raises(ValidationError):
            PolicyReport(reasoning="test")

    def test_adherence_only(self):
        a = AdherenceReport(score=0.9, reasoning="Good", rule_results=[])
        report = PolicyReport(adherence=a, reasoning="ok")
        assert report.adherence is not None
        assert report.coverage is None
        assert report.compliance_score is None

    def test_coverage_only(self):
        c = CoverageReport(score=0.8, reasoning="Good")
        report = PolicyReport(coverage=c, reasoning="ok")
        assert report.coverage is not None
        assert report.adherence is None

    def test_both_metrics(self):
        a = AdherenceReport(score=0.9, reasoning="Good", rule_results=[])
        c = CoverageReport(score=0.8, reasoning="Good")
        report = PolicyReport(
            adherence=a, coverage=c, compliance_score=0.85, reasoning="ok"
        )
        assert report.compliance_score == 0.85

    def test_passed_method(self):
        a = AdherenceReport(score=0.9, reasoning="Good", rule_results=[])
        c = CoverageReport(score=0.8, reasoning="Good")
        report = PolicyReport(
            adherence=a, coverage=c, compliance_score=0.85, reasoning="ok"
        )
        assert report.passed(min_adherence=0.8) is True
        assert report.passed(min_adherence=0.95) is False
        assert report.passed(min_coverage=0.7) is True
        assert report.passed(min_compliance=0.9) is False
