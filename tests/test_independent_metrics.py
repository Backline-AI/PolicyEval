"""Tests for independent metric execution (adherence-only, coverage-only, both)."""

from __future__ import annotations


from policyeval.engine.evaluator import EvaluationEngine
from policyeval.policy.models import AdherenceType, Policy, Rule
from tests.conftest import MockJudge, SequentialMockJudge

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

ADHERENCE_RESPONSE = {
    "rule_results": [{"rule_id": "R1", "score": 1.0, "reasoning": "Pass"}],
    "overall_reasoning": "All good",
}

COVERAGE_RESPONSE = {
    "score": 0.85,
    "reasoning": "All covered",
    "uncovered_actions": [],
}


class TestAdherenceOnly:
    def test_report_has_adherence_only(self):
        judge = MockJudge(ADHERENCE_RESPONSE)
        engine = EvaluationEngine(judge=judge)
        report = engine.evaluate("in", "out", SIMPLE_POLICY, metrics=["adherence"])

        assert report.adherence is not None
        assert report.coverage is None
        assert report.compliance_score is None

    def test_only_one_llm_call(self):
        judge = MockJudge(ADHERENCE_RESPONSE)
        engine = EvaluationEngine(judge=judge)
        engine.evaluate("in", "out", SIMPLE_POLICY, metrics=["adherence"])
        assert len(judge.calls) == 1

    def test_adherence_score_correct(self):
        judge = MockJudge(ADHERENCE_RESPONSE)
        engine = EvaluationEngine(judge=judge)
        report = engine.evaluate("in", "out", SIMPLE_POLICY, metrics=["adherence"])
        assert report.adherence.score == 1.0


class TestCoverageOnly:
    def test_report_has_coverage_only(self):
        judge = MockJudge(COVERAGE_RESPONSE)
        engine = EvaluationEngine(judge=judge)
        report = engine.evaluate("in", "out", SIMPLE_POLICY, metrics=["coverage"])

        assert report.coverage is not None
        assert report.adherence is None
        assert report.compliance_score is None

    def test_only_one_llm_call(self):
        judge = MockJudge(COVERAGE_RESPONSE)
        engine = EvaluationEngine(judge=judge)
        engine.evaluate("in", "out", SIMPLE_POLICY, metrics=["coverage"])
        assert len(judge.calls) == 1

    def test_coverage_score_correct(self):
        judge = MockJudge(COVERAGE_RESPONSE)
        engine = EvaluationEngine(judge=judge)
        report = engine.evaluate("in", "out", SIMPLE_POLICY, metrics=["coverage"])
        assert report.coverage.score == 0.85


class TestBothMetrics:
    def test_report_has_both(self):
        judge = SequentialMockJudge([ADHERENCE_RESPONSE, COVERAGE_RESPONSE])
        engine = EvaluationEngine(judge=judge)
        report = engine.evaluate("in", "out", SIMPLE_POLICY)

        assert report.adherence is not None
        assert report.coverage is not None
        assert report.compliance_score is not None

    def test_two_llm_calls(self):
        judge = SequentialMockJudge([ADHERENCE_RESPONSE, COVERAGE_RESPONSE])
        engine = EvaluationEngine(judge=judge)
        engine.evaluate("in", "out", SIMPLE_POLICY)
        assert len(judge.calls) == 2

    def test_compliance_score_computed(self):
        judge = SequentialMockJudge([ADHERENCE_RESPONSE, COVERAGE_RESPONSE])
        engine = EvaluationEngine(judge=judge)
        report = engine.evaluate("in", "out", SIMPLE_POLICY)
        # adherence=1.0, coverage=0.85 -> harmonic mean
        assert report.compliance_score > 0.85
        assert report.compliance_score <= 1.0


class TestAsyncIndependent:
    async def test_async_adherence_only(self):
        judge = MockJudge(ADHERENCE_RESPONSE)
        engine = EvaluationEngine(judge=judge)
        report = await engine.aevaluate(
            "in", "out", SIMPLE_POLICY, metrics=["adherence"]
        )
        assert report.adherence is not None
        assert report.coverage is None

    async def test_async_both_concurrent(self):
        judge = SequentialMockJudge([ADHERENCE_RESPONSE, COVERAGE_RESPONSE])
        engine = EvaluationEngine(judge=judge)
        report = await engine.aevaluate("in", "out", SIMPLE_POLICY)
        assert report.adherence is not None
        assert report.coverage is not None
