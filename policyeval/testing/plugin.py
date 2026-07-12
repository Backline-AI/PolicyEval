"""Pytest plugin providing assert_policy and CLI flag integration.

Registered automatically via the ``pytest11`` entry point in pyproject.toml:

    [project.entry-points."pytest11"]
    policyeval = "policyeval.testing.plugin"

This means that as soon as ``policyeval`` is installed in the test environment
the plugin is active.  No ``conftest.py`` changes are required.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

try:
    import pytest

    _PYTEST_AVAILABLE = True
except ImportError:
    _PYTEST_AVAILABLE = False

from policyeval.engine.evaluator import MetricName
from policyeval.judges.openai_judge import OpenAIJudge
from policyeval.policy.models import Policy
from policyeval.reporting.models import PolicyReport
from policyeval.testing.test_case import PolicyTest

if TYPE_CHECKING:
    import pytest

# ── Session-level accumulators ──────────────────────────────────────────────

_session_results: list[dict] = []


# ── CLI option registration ──────────────────────────────────────────────────


def pytest_addoption(parser: "pytest.Parser") -> None:
    if not _PYTEST_AVAILABLE:
        return
    group = parser.getgroup("policyeval", "PolicyEval evaluation options")
    group.addoption(
        "--policyeval-model",
        action="store",
        default=None,
        help="Override the LLM judge model for all assert_policy calls.",
    )
    group.addoption(
        "--policyeval-system-prompt",
        action="store",
        default=None,
        help="Override the system prompt (judge persona) for all assert_policy calls.",
    )


# ── Session summary ──────────────────────────────────────────────────────────


def pytest_terminal_summary(
    terminalreporter: "pytest.TerminalReporter",
    exitstatus: int,
    config: "pytest.Config",
) -> None:
    if not _session_results:
        return

    terminalreporter.write_sep("=", "PolicyEval evaluation summary")
    total = len(_session_results)
    passed = sum(1 for r in _session_results if r["passed"])
    failed = total - passed

    terminalreporter.write_line(f"  Total policy assertions   : {total}")
    terminalreporter.write_line(f"  Passed                  : {passed}")
    terminalreporter.write_line(f"  Failed                  : {failed}")

    adherence_scores = [
        r["adherence"] for r in _session_results if r["adherence"] is not None
    ]
    coverage_scores = [
        r["coverage"] for r in _session_results if r["coverage"] is not None
    ]
    compliance_scores = [
        r["compliance"] for r in _session_results if r["compliance"] is not None
    ]

    if adherence_scores:
        avg_a = sum(adherence_scores) / len(adherence_scores)
        terminalreporter.write_line(f"  Avg adherence score     : {avg_a:.3f}")
    if coverage_scores:
        avg_c = sum(coverage_scores) / len(coverage_scores)
        terminalreporter.write_line(f"  Avg coverage score      : {avg_c:.3f}")
    if compliance_scores:
        avg_comp = sum(compliance_scores) / len(compliance_scores)
        terminalreporter.write_line(f"  Avg compliance score    : {avg_comp:.3f}")


# ── Public API ───────────────────────────────────────────────────────────────


def assert_policy(
    output: str,
    policy: Policy,
    *,
    input: Optional[str] = None,
    metrics: Optional[list[MetricName]] = None,
    min_score: Optional[float] = None,
    min_adherence: Optional[float] = None,
    min_coverage: Optional[float] = None,
    min_compliance: Optional[float] = None,
    judge: Optional[object] = None,
    system_prompt: Optional[str] = None,
    eval_mode: str = "batch",
    adherence_weight: float = 1.0,
    coverage_weight: float = 1.0,
    _config: "Optional[pytest.Config]" = None,
) -> PolicyReport:
    """Assert that a model output complies with a policy.

    Runs :class:`~policyeval.testing.test_case.PolicyTest` and raises
    ``AssertionError`` with a detailed message if any threshold is not met.

    Args:
        output: The model's response to evaluate.
        policy: The policy to evaluate against.
        input: Optional original prompt / context. When ``None`` the
            input section is omitted from the judge prompt.
        metrics: Which metrics to compute (default: both).
        min_score: Minimum score applied to the *only* metric when a single
            metric is requested (convenience shorthand for
            ``min_adherence``/``min_coverage``).
        min_adherence: Minimum required adherence score.
        min_coverage: Minimum required coverage score.
        min_compliance: Minimum required compliance score.
        judge: Custom :class:`~policyeval.judges.base.LLMJudge` instance.
        system_prompt: System message for the judge.
        eval_mode: ``"batch"`` or ``"sequential"``.
        adherence_weight: Compliance score adherence weight.
        coverage_weight: Compliance score coverage weight.

    Returns:
        The :class:`~policyeval.reporting.models.PolicyReport` (useful for
        further inspection inside the test).

    Raises:
        AssertionError: When any threshold is not met.

    Example::

        def test_my_policy():
            assert_policy(
                output="I cannot give investment advice.",
                policy=my_policy,
                input="Should I buy Tesla?",
                min_adherence=0.8,
                min_coverage=0.6,
            )
    """
    effective_judge = judge

    # Apply CLI overrides if running inside pytest
    if _config is None:
        try:
            _config = pytest.Config.fromdictargs({}, [])
        except Exception:
            pass

    if effective_judge is None:
        model_override = None
        prompt_override = None
        if _config is not None:
            try:
                model_override = _config.getoption("--policyeval-model", default=None)
                prompt_override = _config.getoption(
                    "--policyeval-system-prompt", default=None
                )
            except (ValueError, AttributeError):
                pass
        model = model_override or "gpt-4o"
        effective_judge = OpenAIJudge(model=model)
        if prompt_override and system_prompt is None:
            system_prompt = prompt_override

    test = PolicyTest(
        input=input,
        output=output,
        policy=policy,
        judge=effective_judge,  # type: ignore[arg-type]
        system_prompt=system_prompt,
        eval_mode=eval_mode,  # type: ignore[arg-type]
        adherence_weight=adherence_weight,
        coverage_weight=coverage_weight,
    )

    report = test.run(metrics=metrics)

    # Resolve min_score shorthand
    resolved_min_adherence = min_adherence
    resolved_min_coverage = min_coverage
    if min_score is not None:
        chosen = list(metrics) if metrics else ["adherence", "coverage"]
        if "adherence" in chosen and resolved_min_adherence is None:
            resolved_min_adherence = min_score
        if "coverage" in chosen and resolved_min_coverage is None:
            resolved_min_coverage = min_score

    _session_results.append(
        {
            "passed": report.passed(
                min_adherence=resolved_min_adherence,
                min_coverage=resolved_min_coverage,
                min_compliance=min_compliance,
            ),
            "adherence": report.adherence.score if report.adherence else None,
            "coverage": report.coverage.score if report.coverage else None,
            "compliance": report.compliance_score,
        }
    )

    _check_thresholds(
        report, resolved_min_adherence, resolved_min_coverage, min_compliance
    )

    return report


# ── Internal helpers ─────────────────────────────────────────────────────────


def _check_thresholds(
    report: PolicyReport,
    min_adherence: Optional[float],
    min_coverage: Optional[float],
    min_compliance: Optional[float],
) -> None:
    failures: list[str] = []

    if min_adherence is not None:
        if report.adherence is None:
            failures.append("Adherence was not evaluated (add 'adherence' to metrics).")
        elif report.adherence.score < min_adherence:
            failures.append(
                f"Adherence score {report.adherence.score:.3f} < required {min_adherence:.3f}.\n"
                f"  Reasoning: {report.adherence.reasoning}\n"
                + _format_violations(report)
            )

    if min_coverage is not None:
        if report.coverage is None:
            failures.append("Coverage was not evaluated (add 'coverage' to metrics).")
        elif report.coverage.score < min_coverage:
            failures.append(
                f"Coverage score {report.coverage.score:.3f} < required {min_coverage:.3f}.\n"
                f"  Reasoning: {report.coverage.reasoning}\n"
                + _format_uncovered(report)
            )

    if min_compliance is not None:
        if report.compliance_score is None:
            failures.append(
                "Compliance score not available (requires both adherence and coverage metrics)."
            )
        elif report.compliance_score < min_compliance:
            failures.append(
                f"Compliance score {report.compliance_score:.3f} < required {min_compliance:.3f}."
            )

    if failures:
        msg = "PolicyEval assertion failed:\n\n" + "\n\n".join(failures)
        raise AssertionError(msg)


def _format_violations(report: PolicyReport) -> str:
    if report.adherence is None or not report.adherence.violations:
        return ""
    lines = ["  Violations:"]
    for v in report.adherence.violations:
        lines.append(f"    [{v.rule_id}] score={v.score} – {v.reasoning}")
    return "\n".join(lines)


def _format_uncovered(report: PolicyReport) -> str:
    if report.coverage is None or not report.coverage.uncovered_actions:
        return ""
    lines = ["  Uncovered actions:"]
    for a in report.coverage.uncovered_actions:
        lines.append(f"    severity={a.severity:.2f} – {a.description}: {a.reasoning}")
    return "\n".join(lines)
