"""Tests for assert_policy and the pytest plugin."""

from __future__ import annotations

import pytest

from policyeval.policy.models import AdherenceType, Policy, Rule
from policyeval.reporting.models import (
    AdherenceReport,
    CoverageReport,
    PolicyReport,
    RuleResult,
)
from policyeval.testing import plugin as plugin_mod
from policyeval.testing.plugin import (
    _check_thresholds,
    _format_uncovered,
    _format_violations,
    assert_policy,
    pytest_terminal_summary,
)
from tests.conftest import SequentialMockJudge


SIMPLE_POLICY = Policy(
    name="Simple",
    rules=[
        Rule(
            id="R1",
            description="Rule one",
            severity=1.0,
            adherence_type=AdherenceType.binary,
        ),
    ],
)

PASS_ADHERENCE_RESPONSE = {
    "rule_results": [{"rule_id": "R1", "score": 1.0, "reasoning": "Pass"}],
    "overall_reasoning": "All pass",
}

FAIL_ADHERENCE_RESPONSE = {
    "rule_results": [{"rule_id": "R1", "score": 0.0, "reasoning": "Violated"}],
    "overall_reasoning": "Failed",
}

COVERAGE_RESPONSE = {
    "score": 0.9,
    "reasoning": "Good coverage",
    "uncovered_actions": [],
}


class TestCheckThresholds:
    """Unit tests for the internal threshold-checking helper."""

    def _pass_report(self):
        a = AdherenceReport(
            score=0.9,
            reasoning="Good",
            rule_results=[
                RuleResult(
                    rule_id="R1",
                    score=1.0,
                    adherence_type=AdherenceType.binary,
                    severity=1.0,
                    reasoning="ok",
                )
            ],
        )
        c = CoverageReport(score=0.8, reasoning="Good")
        return PolicyReport(
            adherence=a, coverage=c, compliance_score=0.85, reasoning="ok"
        )

    def test_passes_all_thresholds(self):
        report = self._pass_report()
        _check_thresholds(
            report, min_adherence=0.8, min_coverage=0.7, min_compliance=0.8
        )

    def test_fails_adherence_threshold(self):
        report = self._pass_report()
        with pytest.raises(AssertionError, match="Adherence score"):
            _check_thresholds(
                report, min_adherence=0.95, min_coverage=None, min_compliance=None
            )

    def test_fails_coverage_threshold(self):
        report = self._pass_report()
        with pytest.raises(AssertionError, match="Coverage score"):
            _check_thresholds(
                report, min_adherence=None, min_coverage=0.95, min_compliance=None
            )

    def test_fails_compliance_threshold(self):
        report = self._pass_report()
        with pytest.raises(AssertionError, match="Compliance score"):
            _check_thresholds(
                report, min_adherence=None, min_coverage=None, min_compliance=0.99
            )

    def test_no_thresholds_always_passes(self):
        report = self._pass_report()
        _check_thresholds(
            report, min_adherence=None, min_coverage=None, min_compliance=None
        )


class TestAssertPolicy:
    def test_passes_when_above_threshold(self):
        judge = SequentialMockJudge([PASS_ADHERENCE_RESPONSE, COVERAGE_RESPONSE])
        report = assert_policy(
            input="test",
            output="test output",
            policy=SIMPLE_POLICY,
            judge=judge,
            min_adherence=0.8,
        )
        assert report.adherence.score == 1.0

    def test_raises_when_below_threshold(self):
        judge = SequentialMockJudge([FAIL_ADHERENCE_RESPONSE, COVERAGE_RESPONSE])
        with pytest.raises(AssertionError, match="PolicyEval assertion failed"):
            assert_policy(
                input="test",
                output="violating output",
                policy=SIMPLE_POLICY,
                judge=judge,
                min_adherence=0.5,
            )

    def test_adherence_only_metric(self):
        judge = SequentialMockJudge([PASS_ADHERENCE_RESPONSE])
        report = assert_policy(
            input="test",
            output="output",
            policy=SIMPLE_POLICY,
            judge=judge,
            metrics=["adherence"],
            min_score=0.5,
        )
        assert report.coverage is None
        assert report.compliance_score is None

    def test_returns_policy_report(self):
        judge = SequentialMockJudge([PASS_ADHERENCE_RESPONSE, COVERAGE_RESPONSE])
        report = assert_policy(
            input="test",
            output="output",
            policy=SIMPLE_POLICY,
            judge=judge,
        )
        assert isinstance(report, PolicyReport)

    def test_min_score_applies_to_single_metric(self):
        judge = SequentialMockJudge([FAIL_ADHERENCE_RESPONSE])
        with pytest.raises(AssertionError):
            assert_policy(
                input="test",
                output="output",
                policy=SIMPLE_POLICY,
                judge=judge,
                metrics=["adherence"],
                min_score=0.8,
            )

    def test_result_recorded_in_session(self):
        before = len(plugin_mod._session_results)
        judge = SequentialMockJudge([PASS_ADHERENCE_RESPONSE, COVERAGE_RESPONSE])
        assert_policy(
            output="output",
            policy=SIMPLE_POLICY,
            judge=judge,
        )
        assert len(plugin_mod._session_results) == before + 1


class TestCheckThresholdsMissingMetrics:
    def test_adherence_requested_but_not_evaluated(self):
        report = PolicyReport(
            coverage=CoverageReport(score=0.9, reasoning="ok"),
            reasoning="coverage only",
        )
        with pytest.raises(AssertionError, match="Adherence was not evaluated"):
            _check_thresholds(
                report, min_adherence=0.5, min_coverage=None, min_compliance=None
            )

    def test_coverage_requested_but_not_evaluated(self):
        report = PolicyReport(
            adherence=AdherenceReport(score=0.9, reasoning="ok"),
            reasoning="adherence only",
        )
        with pytest.raises(AssertionError, match="Coverage was not evaluated"):
            _check_thresholds(
                report, min_adherence=None, min_coverage=0.5, min_compliance=None
            )

    def test_compliance_requested_but_unavailable(self):
        report = PolicyReport(
            adherence=AdherenceReport(score=0.9, reasoning="ok"),
            reasoning="adherence only",
        )
        with pytest.raises(AssertionError, match="Compliance score not available"):
            _check_thresholds(
                report, min_adherence=None, min_coverage=None, min_compliance=0.5
            )


class TestFormatHelpers:
    def test_format_violations_lists_failing_rules(self):
        report = PolicyReport(
            adherence=AdherenceReport(
                score=0.0,
                reasoning="bad",
                rule_results=[
                    RuleResult(
                        rule_id="R1",
                        score=0.0,
                        adherence_type=AdherenceType.binary,
                        severity=1.0,
                        reasoning="Broke the rule",
                    )
                ],
            ),
            reasoning="x",
        )
        text = _format_violations(report)
        assert "R1" in text
        assert "Broke the rule" in text

    def test_format_violations_empty_when_all_pass(self):
        report = PolicyReport(
            adherence=AdherenceReport(score=1.0, reasoning="ok"),
            reasoning="x",
        )
        assert _format_violations(report) == ""

    def test_format_uncovered_lists_actions(self):
        report = PolicyReport(
            coverage=CoverageReport(
                score=0.5,
                reasoning="partial",
                uncovered_actions=[
                    {
                        "description": "Sent an email",
                        "severity": 0.7,
                        "reasoning": "No rule covers email",
                    }
                ],
            ),
            reasoning="x",
        )
        text = _format_uncovered(report)
        assert "Sent an email" in text
        assert "0.70" in text

    def test_format_uncovered_empty_when_none(self):
        report = PolicyReport(
            coverage=CoverageReport(score=1.0, reasoning="all covered"),
            reasoning="x",
        )
        assert _format_uncovered(report) == ""


class _FakeTerminalReporter:
    def __init__(self):
        self.lines: list[str] = []

    def write_sep(self, sep, title):
        self.lines.append(f"=== {title} ===")

    def write_line(self, line):
        self.lines.append(line)


class TestTerminalSummary:
    def test_summary_noop_when_no_results(self, monkeypatch):
        monkeypatch.setattr(plugin_mod, "_session_results", [])
        tr = _FakeTerminalReporter()
        pytest_terminal_summary(tr, 0, None)
        assert tr.lines == []

    def test_summary_prints_averages(self, monkeypatch):
        monkeypatch.setattr(
            plugin_mod,
            "_session_results",
            [
                {"passed": True, "adherence": 1.0, "coverage": 0.8, "compliance": 0.9},
                {
                    "passed": False,
                    "adherence": 0.5,
                    "coverage": 0.6,
                    "compliance": 0.55,
                },
            ],
        )
        tr = _FakeTerminalReporter()
        pytest_terminal_summary(tr, 0, None)
        joined = "\n".join(tr.lines)
        assert "PolicyEval evaluation summary" in joined
        assert "Total policy assertions   : 2" in joined
        assert "Passed                  : 1" in joined
        assert "Avg adherence score" in joined
        assert "Avg coverage score" in joined
        assert "Avg compliance score" in joined
