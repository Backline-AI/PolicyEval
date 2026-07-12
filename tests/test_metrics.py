"""Tests for metrics modules (adherence, coverage, compliance)."""

from policyeval.metrics.adherence import build_adherence_report, compute_adherence_score
from policyeval.metrics.compliance import (
    compute_compliance_score,
    maybe_compute_compliance,
)
from policyeval.metrics.coverage import parse_coverage_response
from policyeval.policy.models import AdherenceType
from policyeval.reporting.models import RuleResult


def make_result(rule_id, score, adherence_type=AdherenceType.binary, severity=1.0):
    return RuleResult(
        rule_id=rule_id,
        score=score,
        adherence_type=adherence_type,
        severity=severity,
        reasoning="test",
    )


class TestAdherenceScoring:
    def test_all_pass_equal_weights(self):
        results = [make_result("R1", 1.0), make_result("R2", 1.0)]
        assert compute_adherence_score(results) == 1.0

    def test_weighted_average(self):
        results = [
            make_result("R1", 1.0, severity=1.0),
            make_result("R2", 0.0, AdherenceType.float, severity=0.5),
        ]
        # Binary R1 passes. Float R2 score=0.0, no binary fail floor.
        # sum(score*sev) / sum(sev) = (1.0*1.0 + 0.0*0.5) / 1.5 = 1.0/1.5 = 0.666...
        score = compute_adherence_score(results)
        assert abs(score - (1.0 / 1.5)) < 1e-9

    def test_binary_fail_floors_to_zero(self):
        results = [
            make_result("R1", 0.0, AdherenceType.binary, severity=1.0),
            make_result("R2", 1.0, AdherenceType.binary, severity=0.5),
        ]
        assert compute_adherence_score(results) == 0.0

    def test_empty_results(self):
        assert compute_adherence_score([]) == 0.0

    def test_all_zero_severity(self):
        results = [make_result("R1", 1.0, severity=0.0)]
        assert compute_adherence_score(results) == 0.0

    def test_build_adherence_report(self):
        results = [make_result("R1", 1.0), make_result("R2", 1.0)]
        report = build_adherence_report(results, "All good")
        assert report.score == 1.0
        assert report.reasoning == "All good"
        assert len(report.rule_results) == 2


class TestComplianceScore:
    def test_equal_weights_both_positive(self):
        score = compute_compliance_score(0.9, 0.9)
        assert abs(score - 0.9) < 1e-9

    def test_imbalance_penalised(self):
        score = compute_compliance_score(0.9, 0.1)
        # Harmonic mean ~ 0.18
        assert score < 0.5

    def test_zero_adherence_arithmetic_fallback(self):
        score = compute_compliance_score(0.0, 0.9)
        # Arithmetic: (0.0 + 0.9) / 2 = 0.45
        assert abs(score - 0.45) < 1e-9

    def test_zero_coverage_arithmetic_fallback(self):
        score = compute_compliance_score(0.9, 0.0)
        assert abs(score - 0.45) < 1e-9

    def test_both_zero(self):
        score = compute_compliance_score(0.0, 0.0)
        assert score == 0.0

    def test_weighted_adherence_heavier(self):
        score_equal = compute_compliance_score(0.8, 0.4, 1.0, 1.0)
        score_adh_heavy = compute_compliance_score(0.8, 0.4, 2.0, 1.0)
        # Heavier adherence weight should pull score closer to adherence (0.8)
        assert score_adh_heavy > score_equal

    def test_maybe_compute_returns_none_when_missing(self):
        assert maybe_compute_compliance(None, 0.9) is None
        assert maybe_compute_compliance(0.9, None) is None
        assert maybe_compute_compliance(None, None) is None

    def test_maybe_compute_returns_score_when_both_present(self):
        result = maybe_compute_compliance(0.8, 0.8)
        assert result is not None
        assert abs(result - 0.8) < 1e-9


class TestCoverageMetric:
    def test_parse_response(self):
        raw = {
            "score": 0.7,
            "reasoning": "One uncovered action",
            "uncovered_actions": [
                {
                    "description": "Modified logging",
                    "severity": 0.3,
                    "reasoning": "No rule.",
                }
            ],
        }
        report = parse_coverage_response(raw)
        assert report.score == 0.7
        assert len(report.uncovered_actions) == 1
        assert report.uncovered_actions[0].severity == 0.3

    def test_parse_empty_uncovered(self):
        raw = {"score": 1.0, "reasoning": "All covered", "uncovered_actions": []}
        report = parse_coverage_response(raw)
        assert report.score == 1.0
        assert report.uncovered_actions == []

    def test_score_clamped(self):
        raw = {"score": 1.5, "reasoning": "Over", "uncovered_actions": []}
        report = parse_coverage_response(raw)
        assert report.score == 1.0
