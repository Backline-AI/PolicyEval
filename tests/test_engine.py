"""Tests for the evaluation engine."""

from __future__ import annotations

import pytest

from policyeval.engine.evaluator import EvaluationEngine
from policyeval.policy.models import AdherenceType, Policy, Rule
from policyeval.reporting.models import RuleResult
from tests.conftest import MockJudge, SequentialMockJudge


def make_engine(response: dict, **kwargs) -> tuple[EvaluationEngine, MockJudge]:
    judge = MockJudge(response)
    engine = EvaluationEngine(judge=judge, **kwargs)
    return engine, judge


BATCH_RESPONSE = {
    "rule_results": [
        {"rule_id": "R1", "score": 1.0, "reasoning": "Passed."},
        {"rule_id": "R2", "score": 0.8, "reasoning": "Mostly passed."},
    ],
    "overall_reasoning": "Output mostly adheres.",
}

COVERAGE_RESPONSE = {
    "score": 0.9,
    "reasoning": "One minor uncovered action.",
    "uncovered_actions": [
        {
            "description": "Extra log line",
            "severity": 0.2,
            "reasoning": "No rule covers it.",
        }
    ],
}

SIMPLE_POLICY = Policy(
    name="Simple",
    rules=[
        Rule(
            id="R1",
            description="Rule one",
            severity=1.0,
            adherence_type=AdherenceType.binary,
        ),
        Rule(
            id="R2",
            description="Rule two",
            severity=0.5,
            adherence_type=AdherenceType.float,
        ),
    ],
)


class TestBatchAdherence:
    def test_batch_evaluation_returns_report(self):
        call_responses = [BATCH_RESPONSE, COVERAGE_RESPONSE]
        judge = SequentialMockJudge(call_responses)
        engine = EvaluationEngine(judge=judge)
        report = engine.evaluate("input", "output", SIMPLE_POLICY)

        assert report.adherence is not None
        assert len(report.adherence.rule_results) == 2
        assert report.adherence.rule_results[0].rule_id == "R1"
        assert report.adherence.rule_results[0].score == 1.0

    def test_binary_score_clamped(self):
        response = {
            "rule_results": [{"rule_id": "R1", "score": 0.7, "reasoning": "Partial"}],
            "overall_reasoning": "partial",
        }
        judge = SequentialMockJudge([response, COVERAGE_RESPONSE])
        engine = EvaluationEngine(judge=judge)
        report = engine.evaluate("input", "output", SIMPLE_POLICY)
        # R1 is binary, score 0.7 => clamped to 1.0 (>= 0.5)
        r1 = next(r for r in report.adherence.rule_results if r.rule_id == "R1")
        assert r1.score == 1.0


class TestSequentialEvaluation:
    def test_sequential_makes_one_call_per_llm_rule(self):
        seq_response = {"rule_id": "R1", "score": 1.0, "reasoning": "Good"}
        seq_response_2 = {"rule_id": "R2", "score": 0.6, "reasoning": "OK"}
        judge = SequentialMockJudge([seq_response, seq_response_2, COVERAGE_RESPONSE])
        engine = EvaluationEngine(judge=judge, eval_mode="sequential")
        report = engine.evaluate("input", "output", SIMPLE_POLICY)
        assert len(report.adherence.rule_results) == 2


class TestProgrammaticEvaluators:
    def test_programmatic_rule_skips_llm(self):
        def my_eval(input, output, rule):
            return RuleResult(
                rule_id=rule.id,
                score=1.0,
                adherence_type=rule.adherence_type,
                severity=rule.severity,
                reasoning="Programmatic pass",
                source="programmatic",
            )

        policy = Policy(
            name="Mixed",
            rules=[
                Rule(
                    id="P1",
                    description="Programmatic",
                    severity=1.0,
                    adherence_type=AdherenceType.binary,
                    evaluator=my_eval,
                ),
                Rule(
                    id="L1",
                    description="LLM rule",
                    severity=0.5,
                    adherence_type=AdherenceType.float,
                ),
            ],
        )
        llm_response = {
            "rule_results": [{"rule_id": "L1", "score": 0.7, "reasoning": "Partial"}],
            "overall_reasoning": "Partial",
        }
        judge = SequentialMockJudge([llm_response, COVERAGE_RESPONSE])
        engine = EvaluationEngine(judge=judge)
        report = engine.evaluate("input", "output", policy)

        p1 = next(r for r in report.adherence.rule_results if r.rule_id == "P1")
        assert p1.source == "programmatic"
        assert p1.score == 1.0

    def test_all_programmatic_no_llm_calls(self):
        def always_pass(input, output, rule):
            return RuleResult(
                rule_id=rule.id,
                score=1.0,
                adherence_type=rule.adherence_type,
                severity=rule.severity,
                reasoning="Pass",
                source="programmatic",
            )

        policy = Policy(
            name="All Prog",
            rules=[
                Rule(
                    id="P1", description="Check 1", severity=1.0, evaluator=always_pass
                ),
                Rule(
                    id="P2", description="Check 2", severity=0.8, evaluator=always_pass
                ),
            ],
        )
        # Use a coverage-only response since adherence requires no LLM calls
        judge = MockJudge(COVERAGE_RESPONSE)
        engine = EvaluationEngine(judge=judge)
        report = engine.evaluate("input", "output", policy)

        # Only the coverage call should have been made
        assert len(judge.calls) == 1
        assert report.adherence.score == 1.0


class TestIndependentMetrics:
    def test_adherence_only(self):
        judge = SequentialMockJudge([BATCH_RESPONSE])
        engine = EvaluationEngine(judge=judge)
        report = engine.evaluate(
            "input", "output", SIMPLE_POLICY, metrics=["adherence"]
        )

        assert report.adherence is not None
        assert report.coverage is None
        assert report.compliance_score is None
        assert len(judge.calls) == 1

    def test_coverage_only(self):
        judge = SequentialMockJudge([COVERAGE_RESPONSE])
        engine = EvaluationEngine(judge=judge)
        report = engine.evaluate("input", "output", SIMPLE_POLICY, metrics=["coverage"])

        assert report.coverage is not None
        assert report.adherence is None
        assert report.compliance_score is None
        assert len(judge.calls) == 1

    def test_both_metrics_computes_compliance(self):
        judge = SequentialMockJudge([BATCH_RESPONSE, COVERAGE_RESPONSE])
        engine = EvaluationEngine(judge=judge)
        report = engine.evaluate("input", "output", SIMPLE_POLICY)

        assert report.adherence is not None
        assert report.coverage is not None
        assert report.compliance_score is not None

    def test_invalid_metrics_raises(self):
        judge = MockJudge({})
        engine = EvaluationEngine(judge=judge)
        with pytest.raises(ValueError):
            engine.evaluate("input", "output", SIMPLE_POLICY, metrics=["invalid"])


class TestComplianceWeights:
    def test_custom_weights_affect_compliance(self):
        resp_same = [BATCH_RESPONSE, COVERAGE_RESPONSE]

        judge1 = SequentialMockJudge(resp_same)
        engine1 = EvaluationEngine(
            judge=judge1, adherence_weight=2.0, coverage_weight=1.0
        )
        r1 = engine1.evaluate("input", "output", SIMPLE_POLICY)

        judge2 = SequentialMockJudge(resp_same)
        engine2 = EvaluationEngine(
            judge=judge2, adherence_weight=1.0, coverage_weight=2.0
        )
        r2 = engine2.evaluate("input", "output", SIMPLE_POLICY)

        # Scores differ because adherence (0.67) < coverage (0.9) in this mock
        assert r1.compliance_score != r2.compliance_score


class TestAsyncEvaluation:
    async def test_async_both_metrics(self):
        judge = SequentialMockJudge([BATCH_RESPONSE, COVERAGE_RESPONSE])
        engine = EvaluationEngine(judge=judge)
        report = await engine.aevaluate("input", "output", SIMPLE_POLICY)

        assert report.adherence is not None
        assert report.coverage is not None
        assert report.compliance_score is not None


class TestContext:
    def test_context_appears_in_batch_adherence_prompt(self):
        judge = SequentialMockJudge([BATCH_RESPONSE, COVERAGE_RESPONSE])
        engine = EvaluationEngine(judge=judge)
        context = "lodash 4.17.20 -> 4.17.21 (pulled in by express upgrade)"

        engine.evaluate("input", "output", SIMPLE_POLICY, context=context)

        adherence_prompt = judge.calls[0][1]
        assert "## Context" in adherence_prompt
        assert context in adherence_prompt

    def test_context_appears_in_coverage_prompt(self):
        judge = SequentialMockJudge([BATCH_RESPONSE, COVERAGE_RESPONSE])
        engine = EvaluationEngine(judge=judge)
        context = "transitive package: qs 6.5.2 -> 6.5.3"

        engine.evaluate("input", "output", SIMPLE_POLICY, context=context)

        coverage_prompt = judge.calls[1][1]
        assert "## Context" in coverage_prompt
        assert context in coverage_prompt

    def test_no_context_section_when_none(self):
        judge = SequentialMockJudge([BATCH_RESPONSE, COVERAGE_RESPONSE])
        engine = EvaluationEngine(judge=judge)

        engine.evaluate("input", "output", SIMPLE_POLICY, context=None)

        for system_prompt, prompt in judge.calls:
            assert "## Context" not in prompt

    def test_context_appears_in_sequential_prompt(self):
        seq_response = {"rule_id": "R1", "score": 1.0, "reasoning": "Good"}
        seq_response_2 = {"rule_id": "R2", "score": 0.9, "reasoning": "OK"}
        judge = SequentialMockJudge([seq_response, seq_response_2, COVERAGE_RESPONSE])
        engine = EvaluationEngine(judge=judge, eval_mode="sequential")
        context = "extra context about changes"

        engine.evaluate("input", "output", SIMPLE_POLICY, context=context)

        for system_prompt, prompt in judge.calls[:2]:
            assert "## Context" in prompt
            assert context in prompt

    def test_context_in_coverage_only_mode(self):
        judge = SequentialMockJudge([COVERAGE_RESPONSE])
        engine = EvaluationEngine(judge=judge)
        context = "derived change context"

        engine.evaluate(
            "input", "output", SIMPLE_POLICY, context=context, metrics=["coverage"]
        )

        coverage_prompt = judge.calls[0][1]
        assert "## Context" in coverage_prompt
        assert context in coverage_prompt


_SHAPE_MARKER = "Return a JSON object with this exact shape:"


def json_shape(prompt: str) -> str:
    """The requested-JSON block of a judge prompt, without the prose around it.

    The prose deliberately names both "reasoning" and "score" in the right
    order, so an ordering assertion over the whole prompt passes even when the
    shape itself is wrong. Ordering must be checked against the shape.
    """
    start = prompt.index(_SHAPE_MARKER) + len(_SHAPE_MARKER)
    end = prompt.index("\n}", start)
    return prompt[start:end]


def key_order(block: str, *keys: str) -> list[int]:
    """Positions of each key in *block*, asserting each one appears exactly once."""
    positions = []
    for key in keys:
        quoted = f'"{key}"'
        assert block.count(quoted) == 1, f"{quoted} appears {block.count(quoted)}x"
        positions.append(block.index(quoted))
    return positions


class TestReasonBeforeScore:
    """The judge writes JSON left to right, so a "score" emitted before its
    "reasoning" is committed before the analysis that should decide it exists.

    Observed in production: a rule requiring "at least 1.18.0" was scored 0.0
    against a resolved 1.20.0, and the reasoning field then read "…Wait,
    1.20.0 >= 1.18.0, so this is actually satisfied." The judge reached the
    right answer one field too late and the 0.0 propagated as a hard failure.
    These tests pin the key order in every prompt that asks for a score.
    """

    def test_batch_adherence_shape_puts_reasoning_before_score(self):
        judge = SequentialMockJudge([BATCH_RESPONSE, COVERAGE_RESPONSE])
        engine = EvaluationEngine(judge=judge)

        engine.evaluate("input", "output", SIMPLE_POLICY)

        shape = json_shape(judge.calls[0][1])
        rule_id, reasoning, score = key_order(shape, "rule_id", "reasoning", "score")
        assert rule_id < reasoning < score, shape

    def test_batch_adherence_bullet_list_puts_reasoning_before_score(self):
        """The per-key bullet list above the shape is read as authoritative too."""
        judge = SequentialMockJudge([BATCH_RESPONSE, COVERAGE_RESPONSE])
        engine = EvaluationEngine(judge=judge)

        engine.evaluate("input", "output", SIMPLE_POLICY)

        bullets = judge.calls[0][1].split(_SHAPE_MARKER)[0]
        assert bullets.index('- "reasoning"') < bullets.index('- "score"'), bullets

    def test_sequential_adherence_shape_puts_reasoning_before_score(self):
        seq_response = {"rule_id": "R1", "reasoning": "Good", "score": 1.0}
        seq_response_2 = {"rule_id": "R2", "reasoning": "OK", "score": 0.9}
        judge = SequentialMockJudge([seq_response, seq_response_2, COVERAGE_RESPONSE])
        engine = EvaluationEngine(judge=judge, eval_mode="sequential")

        engine.evaluate("input", "output", SIMPLE_POLICY)

        for _system_prompt, prompt in judge.calls[:2]:
            shape = json_shape(prompt)
            reasoning, score = key_order(shape, "reasoning", "score")
            assert reasoning < score, shape

    def test_coverage_shape_puts_every_reasoning_before_its_score(self):
        judge = SequentialMockJudge([COVERAGE_RESPONSE])
        engine = EvaluationEngine(judge=judge)

        engine.evaluate("input", "output", SIMPLE_POLICY, metrics=["coverage"])

        shape = json_shape(judge.calls[0][1])
        # Per-action severity is a score too, so it follows its own reasoning;
        # the overall score comes last, after the actions it summarises.
        description, severity, score = key_order(
            shape, "description", "severity", "score"
        )
        action_reasoning, overall_reasoning = sorted(
            m for m in _reasoning_positions(shape)
        )
        assert description < action_reasoning < severity, shape
        assert overall_reasoning < score, shape
        assert severity < overall_reasoning, shape

    def test_every_scoring_prompt_states_the_ordering_requirement(self):
        """Key order alone is a hint; the instruction is what survives a judge
        that reorders keys on its own."""
        judge = SequentialMockJudge([BATCH_RESPONSE, COVERAGE_RESPONSE])
        engine = EvaluationEngine(judge=judge)

        engine.evaluate("input", "output", SIMPLE_POLICY)

        for _system_prompt, prompt in judge.calls:
            assert "Emit the keys in exactly the order shown" in prompt

    def test_reordered_response_keys_still_parse(self):
        """Nothing downstream depends on order — the parsers read by key."""
        reordered = {
            "rule_results": [
                {"reasoning": "Passed.", "score": 1.0, "rule_id": "R1"},
                {"score": 0.8, "rule_id": "R2", "reasoning": "Mostly."},
            ],
            "overall_reasoning": "Fine.",
        }
        judge = SequentialMockJudge([reordered, COVERAGE_RESPONSE])
        engine = EvaluationEngine(judge=judge)

        report = engine.evaluate("input", "output", SIMPLE_POLICY)

        assert report.adherence is not None
        r1 = next(r for r in report.adherence.rule_results if r.rule_id == "R1")
        assert r1.score == 1.0
        assert r1.reasoning == "Passed."


def _reasoning_positions(block: str) -> list[int]:
    """Every `"reasoning"` position in *block* (the coverage shape has two)."""
    positions = []
    start = 0
    while (found := block.find('"reasoning"', start)) != -1:
        positions.append(found)
        start = found + 1
    assert len(positions) == 2, positions
    return positions
