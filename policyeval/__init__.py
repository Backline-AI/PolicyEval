"""PolicyEval – LLM policy compliance evaluation and execution.

Public API
----------

Policy definition::

    from policyeval import Policy, Rule

Evaluation::

    from policyeval import PolicyTest

Execution (policy-guided generation)::

    from policyeval import PolicyExecutor

Programmatic evaluator result::

    from policyeval import RuleResult

Reports::

    from policyeval import PolicyReport, AdherenceReport, CoverageReport, ExecutionResult

Pytest integration::

    from policyeval import assert_policy

Rule extraction from text::

    from policyeval import extract_rules, extract_rules_async

Policy loading::

    from policyeval import load_policy, load_policy_from_dict, load_policy_from_string

LLM primitives::

    from policyeval.llm import LLM, OpenAILLM

Judges::

    from policyeval.judges.openai_judge import OpenAIJudge
    from policyeval.judges.base import LLMJudge
"""

from policyeval.policy.models import AdherenceType, Policy, Rule
from policyeval.policy.loader import (
    load_policy,
    load_policy_from_dict,
    load_policy_from_string,
)
from policyeval.policy.extractor import extract_rules, extract_rules_async
from policyeval.reporting.models import (
    AdherenceReport,
    CoverageReport,
    ExecutionResult,
    MetricReport,
    PolicyReport,
    RuleResult,
    UncoveredAction,
)
from policyeval.testing.test_case import PolicyTest
from policyeval.testing.executor import PolicyExecutor

try:
    from policyeval.testing.plugin import assert_policy
except ImportError:
    pass
from policyeval.llm.base import LLM
from policyeval.llm.openai import OpenAILLM

__all__ = [
    # Policy definition
    "AdherenceType",
    "Policy",
    "Rule",
    # Policy loading
    "load_policy",
    "load_policy_from_dict",
    "load_policy_from_string",
    # Rule extraction
    "extract_rules",
    "extract_rules_async",
    # Reports
    "MetricReport",
    "RuleResult",
    "UncoveredAction",
    "AdherenceReport",
    "CoverageReport",
    "PolicyReport",
    "ExecutionResult",
    # Evaluation API
    "PolicyTest",
    # Execution API
    "PolicyExecutor",
    # Pytest integration
    "assert_policy",
    # LLM primitives
    "LLM",
    "OpenAILLM",
]
