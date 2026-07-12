"""Tests for policy domain models (Rule and Policy)."""

import pytest
from pydantic import ValidationError

from policyeval.policy.models import AdherenceType, Policy, Rule


class TestRule:
    def test_defaults(self):
        rule = Rule(id="R1", description="Test rule")
        assert rule.severity == 1.0
        assert rule.adherence_type == AdherenceType.binary
        assert rule.scope is None
        assert rule.evaluator is None

    def test_custom_values(self):
        rule = Rule(
            id="R2",
            description="Soft rule",
            severity=0.6,
            adherence_type=AdherenceType.float,
            scope="financial queries",
        )
        assert rule.severity == 0.6
        assert rule.adherence_type == AdherenceType.float

    def test_severity_out_of_range(self):
        with pytest.raises(ValidationError):
            Rule(id="R1", description="Bad rule", severity=1.5)

    def test_severity_negative(self):
        with pytest.raises(ValidationError):
            Rule(id="R1", description="Bad rule", severity=-0.1)

    def test_string_adherence_type(self):
        rule = Rule(id="R1", description="Float rule", adherence_type="float")
        assert rule.adherence_type == AdherenceType.float

    def test_with_evaluator(self):
        def my_eval(input, output, rule):
            pass

        rule = Rule(id="R1", description="Prog rule", evaluator=my_eval)
        assert rule.evaluator is my_eval


class TestPolicy:
    def test_basic(self):
        policy = Policy(
            name="Test",
            rules=[Rule(id="R1", description="Rule one")],
        )
        assert policy.name == "Test"
        assert len(policy.rules) == 1

    def test_empty_rules_raises(self):
        with pytest.raises(ValidationError):
            Policy(name="Empty", rules=[])

    def test_get_rule(self):
        policy = Policy(
            name="P",
            rules=[
                Rule(id="R1", description="Rule one"),
                Rule(id="R2", description="Rule two"),
            ],
        )
        assert policy.get_rule("R1").id == "R1"
        assert policy.get_rule("missing") is None

    def test_from_dict(self):
        data = {
            "name": "Dict Policy",
            "rules": [
                {
                    "id": "R1",
                    "description": "First rule",
                    "severity": 0.9,
                    "adherence_type": "binary",
                }
            ],
        }
        policy = Policy.model_validate(data)
        assert policy.name == "Dict Policy"
        assert policy.rules[0].severity == 0.9
