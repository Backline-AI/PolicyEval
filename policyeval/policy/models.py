"""Core policy domain models: Rule and Policy."""

from __future__ import annotations

from enum import Enum
from typing import Callable, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class AdherenceType(str, Enum):
    """How a rule's adherence score is interpreted.

    binary: the judge returns strictly 0 (fail) or 1 (pass).
    float: the judge returns a continuous score in [0, 1].
    """

    binary = "binary"
    float = "float"


class Rule(BaseModel):
    """A single evaluable requirement within a policy.

    Attributes:
        id: Unique identifier used to correlate results back to this rule.
        description: Human-readable statement of the requirement. This is
            the text shown to the LLM judge.
        severity: User-defined weight (0–1) applied when computing the
            weighted adherence score. Defaults to 1.0 (maximum weight).
        adherence_type: Scoring mode. ``binary`` means strictly 0 or 1;
            ``float`` means the judge returns a continuous 0–1 score.
        scope: Optional free-text hint that limits when this rule applies
            (e.g. "investment-related queries"). Included in the prompt.
        evaluator: Optional Python callable that evaluates the rule
            without calling the LLM. Signature::

                (input: str, output: str, rule: Rule) -> RuleResult

            When set, this rule is skipped by the LLM judge entirely.
    """

    model_config = {"arbitrary_types_allowed": True}

    id: str
    description: str
    severity: float = Field(default=1.0, ge=0.0, le=1.0)
    adherence_type: AdherenceType = AdherenceType.binary
    scope: Optional[str] = None
    evaluator: Optional[Callable] = None

    @field_validator("severity")
    @classmethod
    def _severity_range(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError("severity must be between 0.0 and 1.0")
        return v


class Policy(BaseModel):
    """A named collection of rules that an LLM output is evaluated against.

    Attributes:
        name: Human-readable policy name.
        description: Optional explanation of what this policy governs.
        rules: Ordered list of :class:`Rule` objects.
        version: Optional semver or free-text version string.
    """

    name: str
    description: Optional[str] = None
    rules: list[Rule] = Field(default_factory=list)
    version: Optional[str] = None

    @model_validator(mode="after")
    def _rules_not_empty(self) -> "Policy":
        if len(self.rules) == 0:
            raise ValueError("Policy must contain at least one rule")
        return self

    def get_rule(self, rule_id: str) -> Optional[Rule]:
        """Return the rule with the given id, or None if not found."""
        for rule in self.rules:
            if rule.id == rule_id:
                return rule
        return None
