"""Shared pytest fixtures for all test modules."""

from __future__ import annotations

import json

import pytest

from policyeval.judges.base import LLMJudge
from policyeval.policy.models import AdherenceType, Policy, Rule


# ── Mock judge ──────────────────────────────────────────────────────────────


class MockJudge(LLMJudge):
    """A deterministic mock judge for unit testing (no API calls)."""

    def __init__(self, response: dict) -> None:
        self.response = response
        self.calls: list[tuple[str, str]] = []

    async def complete(self, system_prompt: str, prompt: str) -> str:
        self.calls.append((system_prompt, prompt))
        return json.dumps(self.response)

    def complete_sync(self, system_prompt: str, prompt: str) -> str:
        self.calls.append((system_prompt, prompt))
        return json.dumps(self.response)

    async def evaluate(self, system_prompt: str, prompt: str) -> dict:
        self.calls.append((system_prompt, prompt))
        return self.response

    def evaluate_sync(self, system_prompt: str, prompt: str) -> dict:
        self.calls.append((system_prompt, prompt))
        return self.response


class SequentialMockJudge(LLMJudge):
    """A mock judge that returns a different response for each call."""

    def __init__(self, responses: list[dict]) -> None:
        self._responses = list(responses)
        self._index = 0
        self.calls: list[tuple[str, str]] = []

    def _next(self) -> dict:
        resp = self._responses[self._index % len(self._responses)]
        self._index += 1
        return resp

    async def complete(self, system_prompt: str, prompt: str) -> str:
        self.calls.append((system_prompt, prompt))
        return json.dumps(self._next())

    def complete_sync(self, system_prompt: str, prompt: str) -> str:
        self.calls.append((system_prompt, prompt))
        return json.dumps(self._next())

    async def evaluate(self, system_prompt: str, prompt: str) -> dict:
        self.calls.append((system_prompt, prompt))
        return self._next()

    def evaluate_sync(self, system_prompt: str, prompt: str) -> dict:
        self.calls.append((system_prompt, prompt))
        return self._next()


# ── Sample policies ─────────────────────────────────────────────────────────


@pytest.fixture
def binary_rule() -> Rule:
    return Rule(
        id="R1",
        description="Must not do X",
        severity=1.0,
        adherence_type=AdherenceType.binary,
    )


@pytest.fixture
def float_rule() -> Rule:
    return Rule(
        id="R2",
        description="Should include disclaimer",
        severity=0.5,
        adherence_type=AdherenceType.float,
    )


@pytest.fixture
def simple_policy(binary_rule, float_rule) -> Policy:
    return Policy(name="Test Policy", rules=[binary_rule, float_rule])


@pytest.fixture
def all_binary_policy() -> Policy:
    return Policy(
        name="Binary Policy",
        rules=[
            Rule(
                id="R1",
                description="Rule 1",
                severity=1.0,
                adherence_type=AdherenceType.binary,
            ),
            Rule(
                id="R2",
                description="Rule 2",
                severity=0.8,
                adherence_type=AdherenceType.binary,
            ),
        ],
    )


@pytest.fixture
def mock_batch_response() -> dict:
    return {
        "rule_results": [
            {"rule_id": "R1", "score": 1.0, "reasoning": "Rule R1 is satisfied."},
            {
                "rule_id": "R2",
                "score": 0.8,
                "reasoning": "Rule R2 is mostly satisfied.",
            },
        ],
        "overall_reasoning": "The output mostly adheres to the policy.",
    }


@pytest.fixture
def mock_coverage_response() -> dict:
    return {
        "score": 0.7,
        "reasoning": "One uncovered action found.",
        "uncovered_actions": [
            {
                "description": "Modified logging config",
                "severity": 0.4,
                "reasoning": "No rule covers logging changes.",
            }
        ],
    }
