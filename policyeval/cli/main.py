"""Typer CLI for PolicyEval.

Usage::

    policyeval run policy.yaml outputs.json
    policyeval run policy.yaml outputs.json --eval-mode sequential
    policyeval run policy.yaml outputs.json -o report.json
    policyeval run policy.yaml outputs.json --system-prompt "You are a security expert..."
    policyeval run policy.yaml outputs.json --metrics adherence
    policyeval run policy.yaml outputs.json --format markdown
    policyeval run policy.yaml outputs.json --format json
    policyeval execute policy.yaml --input "Should I buy Tesla stock?"
    policyeval execute policy.yaml inputs.json -o results.json
    policyeval extract policy.md -o policy.yaml
    policyeval validate policy.yaml
"""

from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
from typing import Optional

import typer
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

from policyeval.engine.evaluator import EvaluationEngine
from policyeval.engine.executor import ExecutionEngine
from policyeval.judges.openai_judge import OpenAIJudge
from policyeval.llm.openai import OpenAILLM
from policyeval.policy.extractor import extract_rules
from policyeval.policy.loader import load_policy
from policyeval.policy.models import Policy
from policyeval.reporting.models import ExecutionResult, PolicyReport

app = typer.Typer(
    name="policyeval",
    help="LLM policy compliance evaluation and execution.",
    add_completion=False,
)
console = Console()
err_console = Console(stderr=True)


class EvalModeChoice(str, Enum):
    batch = "batch"
    sequential = "sequential"


class MetricChoice(str, Enum):
    adherence = "adherence"
    coverage = "coverage"
    both = "both"


class FormatChoice(str, Enum):
    text = "text"
    markdown = "markdown"
    json = "json"


@app.command("run")
def run(
    policy_file: Path = typer.Argument(..., help="Path to policy YAML or JSON file."),
    interactions_file: Path = typer.Argument(
        ...,
        help=(
            "Path to a YAML or JSON file containing the interactions to evaluate — "
            "each an input paired with the response it produced. "
            'Accepts a single object {"input": "...", "output": "...", "context": "..."} '
            "or an array of them. "
            'The "context" field is optional; use it to provide extra context for changes '
            "not covered by policy rules (e.g. transitive dependency upgrades)."
        ),
    ),
    output_file: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Save the report(s) to this file (Markdown when --format markdown, else JSON).",
    ),
    model: str = typer.Option("gpt-4o", "--model", "-m", help="LLM judge model."),
    system_prompt: Optional[str] = typer.Option(
        None,
        "--system-prompt",
        "-s",
        help="Custom system prompt for the judge persona.",
    ),
    eval_mode: EvalModeChoice = typer.Option(
        EvalModeChoice.batch,
        "--eval-mode",
        "-e",
        help="Evaluation mode: batch or sequential.",
    ),
    metrics: MetricChoice = typer.Option(
        MetricChoice.both, "--metrics", help="Which metrics to compute."
    ),
    output_format: FormatChoice = typer.Option(
        FormatChoice.text,
        "--format",
        "-f",
        help="How to render the report(s) to stdout: text, markdown, or json.",
    ),
    threshold: float = typer.Option(
        0.5,
        "--threshold",
        min=0.0,
        max=1.0,
        help="Pass/fail cutoff for a score (0–1). A score below it is marked FAIL.",
    ),
    adherence_weight: float = typer.Option(
        1.0, "--adherence-weight", help="Weight for adherence in compliance score."
    ),
    coverage_weight: float = typer.Option(
        1.0, "--coverage-weight", help="Weight for coverage in compliance score."
    ),
    base_url: Optional[str] = typer.Option(
        None, "--base-url", help="Base URL for OpenAI-compatible proxy (e.g. LiteLLM)."
    ),
) -> None:
    """Evaluate LLM outputs against a policy and print a compliance report."""
    if not policy_file.exists():
        err_console.print(f"[red]Error:[/red] Policy file not found: {policy_file}")
        raise typer.Exit(code=1)
    if not interactions_file.exists():
        err_console.print(
            f"[red]Error:[/red] Interactions file not found: {interactions_file}"
        )
        raise typer.Exit(code=1)

    try:
        policy = load_policy(policy_file)
    except Exception as exc:
        err_console.print(f"[red]Failed to load policy:[/red] {exc}")
        raise typer.Exit(code=1)

    try:
        with interactions_file.open("r", encoding="utf-8") as fh:
            # yaml.safe_load parses both YAML and JSON, so a single call
            # handles .yaml, .yml, and .json interaction files.
            interactions_data = yaml.safe_load(fh)
    except Exception as exc:
        err_console.print(f"[red]Failed to parse interactions file:[/red] {exc}")
        raise typer.Exit(code=1)

    # Accept either a single interaction object or an array of them.
    if isinstance(interactions_data, dict):
        interactions_data = [interactions_data]
    elif not isinstance(interactions_data, list):
        err_console.print(
            "[red]Error:[/red] Interactions file must contain a JSON object or array."
        )
        raise typer.Exit(code=1)

    judge = OpenAIJudge(model=model, base_url=base_url)
    engine = EvaluationEngine(
        judge=judge,
        system_prompt=system_prompt,
        eval_mode=eval_mode.value,  # type: ignore[arg-type]
        adherence_weight=adherence_weight,
        coverage_weight=coverage_weight,
    )

    metric_list: Optional[list[str]] = None
    if metrics == MetricChoice.adherence:
        metric_list = ["adherence"]
    elif metrics == MetricChoice.coverage:
        metric_list = ["coverage"]

    # In JSON mode stdout must stay valid JSON, so progress and per-item
    # rendering are routed to stderr and the reports are emitted as one array
    # at the end.
    as_json = output_format == FormatChoice.json
    progress_console = err_console if as_json else console

    reports: list[PolicyReport] = []
    for i, item in enumerate(interactions_data):
        if not isinstance(item, dict):
            err_console.print(
                f"[yellow]Warning:[/yellow] Skipping item {i} – not a JSON object."
            )
            continue
        input_text = str(item.get("input", ""))
        output_text = str(item.get("output", ""))
        context_text = item.get("context") or None

        progress_console.print(
            f"\n[bold]Evaluating item {i + 1}/{len(interactions_data)}…[/bold]"
        )
        try:
            report = engine.evaluate(
                input_text,
                output_text,
                policy,
                context=context_text,
                metrics=metric_list,  # type: ignore[arg-type]
            )
            reports.append(report)
            if output_format == FormatChoice.markdown:
                console.print(
                    _report_to_markdown(report, index=i + 1, threshold=threshold)
                )
            elif not as_json:
                _print_report(report, index=i + 1, threshold=threshold)
        except Exception as exc:
            err_console.print(f"[red]Evaluation error for item {i + 1}:[/red] {exc}")
            raise typer.Exit(code=1)

    if as_json:
        print(
            json.dumps(
                [r.model_dump(mode="json") for r in reports], indent=2, default=str
            )
        )

    if output_file:
        # Save in the chosen format: Markdown when --format markdown, otherwise
        # the full JSON report (the default for text and json formats).
        if output_format == FormatChoice.markdown:
            content = "\n\n".join(
                _report_to_markdown(r, index=i + 1, threshold=threshold)
                for i, r in enumerate(reports)
            )
            output_file.write_text(content + "\n", encoding="utf-8")
        else:
            data = [r.model_dump(mode="json") for r in reports]
            with output_file.open("w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2, default=str)
        progress_console.print(f"\n[green]Report saved to {output_file}[/green]")


@app.command("execute")
def execute(
    policy_file: Path = typer.Argument(..., help="Path to policy YAML or JSON file."),
    input_arg: Optional[str] = typer.Option(
        None,
        "--input",
        "-i",
        help="Input text (user query) to generate a response for.",
    ),
    inputs_file: Optional[Path] = typer.Argument(
        None,
        help=(
            "Optional path to a JSON file containing inputs to execute. "
            'Expected format: [{"input": "..."}] or [{"input": "...", "id": "..."}]'
        ),
    ),
    output_file: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Save the result(s) to this JSON file."
    ),
    model: str = typer.Option(
        "gpt-4o", "--model", "-m", help="LLM model for generation."
    ),
    temperature: float = typer.Option(
        0.7, "--temperature", "-t", help="Sampling temperature (default 0.7)."
    ),
    system_prompt: Optional[str] = typer.Option(
        None,
        "--system-prompt",
        "-s",
        help="Custom system prompt / persona for the generator.",
    ),
    base_url: Optional[str] = typer.Option(
        None, "--base-url", help="Base URL for OpenAI-compatible proxy (e.g. LiteLLM)."
    ),
) -> None:
    """Generate policy-compliant LLM output for one or more inputs.

    Provide either --input for a single query, or a JSON inputs file for batch execution.
    """
    if not policy_file.exists():
        err_console.print(f"[red]Error:[/red] Policy file not found: {policy_file}")
        raise typer.Exit(code=1)

    if input_arg is None and inputs_file is None:
        err_console.print(
            "[red]Error:[/red] Provide either --input or an inputs file argument."
        )
        raise typer.Exit(code=1)

    if inputs_file is not None and not inputs_file.exists():
        err_console.print(f"[red]Error:[/red] Inputs file not found: {inputs_file}")
        raise typer.Exit(code=1)

    try:
        policy = load_policy(policy_file)
    except Exception as exc:
        err_console.print(f"[red]Failed to load policy:[/red] {exc}")
        raise typer.Exit(code=1)

    # Build the list of inputs to process
    inputs: list[str] = []
    if input_arg is not None:
        inputs = [input_arg]
    else:
        try:
            with inputs_file.open("r", encoding="utf-8") as fh:  # type: ignore[union-attr]
                inputs_data = json.load(fh)
        except Exception as exc:
            err_console.print(f"[red]Failed to parse inputs file:[/red] {exc}")
            raise typer.Exit(code=1)
        if not isinstance(inputs_data, list):
            err_console.print(
                "[red]Error:[/red] Inputs file must contain a JSON array."
            )
            raise typer.Exit(code=1)
        for item in inputs_data:
            if isinstance(item, dict):
                inputs.append(str(item.get("input", "")))
            elif isinstance(item, str):
                inputs.append(item)

    llm = OpenAILLM(model=model, temperature=temperature, base_url=base_url)
    engine = ExecutionEngine(llm=llm, system_prompt=system_prompt)

    results: list[ExecutionResult] = []
    for i, input_text in enumerate(inputs):
        console.print(f"\n[bold]Executing item {i + 1}/{len(inputs)}…[/bold]")
        try:
            result = engine.execute_sync(input_text, policy)
            results.append(result)
            _print_execution_result(result, index=i + 1)
        except Exception as exc:
            err_console.print(f"[red]Execution error for item {i + 1}:[/red] {exc}")
            raise typer.Exit(code=1)

    if output_file:
        data = [r.model_dump(mode="json") for r in results]
        with output_file.open("w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, default=str)
        console.print(f"\n[green]Results saved to {output_file}[/green]")


@app.command("extract")
def extract(
    text_file: Path = typer.Argument(
        ..., help="Path to a plain-text or Markdown file describing the policy."
    ),
    output_file: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Write the generated policy YAML here (defaults to stdout).",
    ),
    name: Optional[str] = typer.Option(
        None,
        "--name",
        "-n",
        help="Policy name (defaults to the source file's stem).",
    ),
    adherence_type: str = typer.Option(
        "binary",
        "--adherence-type",
        help="Default adherence_type for extracted rules: 'binary' or 'float'.",
    ),
    severity: float = typer.Option(
        1.0, "--severity", help="Default severity (0–1) for extracted rules."
    ),
    model: str = typer.Option(
        "gpt-4o", "--model", "-m", help="LLM model used for extraction."
    ),
    system_prompt: Optional[str] = typer.Option(
        None,
        "--system-prompt",
        "-s",
        help="Custom system prompt / persona for the extractor.",
    ),
    base_url: Optional[str] = typer.Option(
        None, "--base-url", help="Base URL for OpenAI-compatible proxy (e.g. LiteLLM)."
    ),
) -> None:
    """Turn a plain-English policy document into a structured policy YAML.

    Reads free-form text (a Markdown policy doc, a requirements list, etc.) and
    uses an LLM to decompose it into individually evaluable rules.
    """
    if not text_file.exists():
        err_console.print(f"[red]Error:[/red] File not found: {text_file}")
        raise typer.Exit(code=1)

    text = text_file.read_text(encoding="utf-8")
    if not text.strip():
        err_console.print(f"[red]Error:[/red] File is empty: {text_file}")
        raise typer.Exit(code=1)

    llm = OpenAILLM(model=model, base_url=base_url)
    try:
        rules = extract_rules(
            text=text,
            llm=llm,
            system_prompt=system_prompt,
            default_adherence_type=adherence_type,
            default_severity=severity,
        )
    except Exception as exc:
        err_console.print(f"[red]Extraction failed:[/red] {exc}")
        raise typer.Exit(code=1)

    policy = Policy(name=name or text_file.stem, rules=rules)
    yaml_text = _policy_to_yaml(policy)

    if output_file:
        output_file.write_text(yaml_text, encoding="utf-8")
        console.print(f"[green]Extracted {len(rules)} rule(s) → {output_file}[/green]")
    else:
        console.print(yaml_text)


@app.command("validate")
def validate(
    policy_file: Path = typer.Argument(
        ..., help="Path to policy YAML or JSON file to validate."
    ),
) -> None:
    """Validate a policy file without running an evaluation."""
    if not policy_file.exists():
        err_console.print(f"[red]Error:[/red] File not found: {policy_file}")
        raise typer.Exit(code=1)

    try:
        policy = load_policy(policy_file)
    except Exception as exc:
        err_console.print(f"[red]Invalid policy:[/red] {exc}")
        raise typer.Exit(code=1)

    console.print(
        Panel(
            f"[green]Valid[/green]\n\n"
            f"Name    : {policy.name}\n"
            f"Version : {policy.version or 'n/a'}\n"
            f"Rules   : {len(policy.rules)}",
            title="Policy Validation",
        )
    )
    table = Table("ID", "Type", "Severity", "Description", box=box.SIMPLE)
    for rule in policy.rules:
        table.add_row(
            rule.id,
            rule.adherence_type.value,
            f"{rule.severity:.2f}",
            rule.description[:60] + ("…" if len(rule.description) > 60 else ""),
        )
    console.print(table)


# ── Helpers ──────────────────────────────────────────────────────────────────


def _policy_to_yaml(policy: Policy) -> str:
    """Serialize a :class:`Policy` to human-friendly YAML (loadable by ``load_policy``)."""
    data: dict = {"name": policy.name}
    if policy.version:
        data["version"] = policy.version
    if policy.description:
        data["description"] = policy.description

    rules: list[dict] = []
    for rule in policy.rules:
        rule_dict: dict = {
            "id": rule.id,
            "description": rule.description,
            "severity": rule.severity,
            "adherence_type": rule.adherence_type.value,
        }
        if rule.scope:
            rule_dict["scope"] = rule.scope
        rules.append(rule_dict)
    data["rules"] = rules

    return yaml.safe_dump(data, sort_keys=False, allow_unicode=True, indent=2)


def _print_report(report: PolicyReport, index: int, threshold: float = 0.5) -> None:
    parts = []

    def status(score: float) -> str:
        return "[green]PASS[/green]" if score >= threshold else "[red]FAIL[/red]"

    if report.adherence is not None:
        a = report.adherence
        parts.append(f"Adherence : {a.score:.3f} {status(a.score)}")
        if a.violations:
            for v in a.violations:
                parts.append(f"  ✗ [{v.rule_id}] {v.reasoning[:80]}")

    if report.coverage is not None:
        c = report.coverage
        parts.append(f"Coverage  : {c.score:.3f} {status(c.score)}")
        if c.uncovered_actions:
            for ua in c.uncovered_actions:
                parts.append(f"  ↑ (sev={ua.severity:.2f}) {ua.description[:80]}")

    if report.compliance_score is not None:
        parts.append(
            f"Compliance: {report.compliance_score:.3f} "
            f"{status(report.compliance_score)}"
        )

    console.print(
        Panel("\n".join(parts), title=f"Result #{index}", border_style="blue")
    )


def _report_to_markdown(
    report: PolicyReport, index: int, threshold: float = 0.5
) -> str:
    """Render a :class:`PolicyReport` as a self-contained Markdown block."""
    lines: list[str] = [f"### Result #{index}"]

    def verdict(score: float) -> str:
        return "PASS" if score >= threshold else "FAIL"

    if report.adherence is not None:
        a = report.adherence
        lines.append("")
        lines.append(f"**Adherence — {a.score:.2f} ({verdict(a.score)})**")
        if a.rule_results:
            lines.append("")
            for r in a.rule_results:
                mark = "✅" if r.passed else "❌"
                lines.append(f"- {mark} `{r.rule_id}` — {r.score:.2f}")

    if report.coverage is not None:
        c = report.coverage
        lines.append("")
        lines.append(f"**Coverage — {c.score:.2f} ({verdict(c.score)})**")
        if c.uncovered_actions:
            lines.append("")
            for ua in c.uncovered_actions:
                lines.append(
                    f"- ⚠️ {ua.description} _(severity {ua.severity:.2f})_ — {ua.reasoning}"
                )

    if report.compliance_score is not None:
        lines.append("")
        lines.append(
            f"**Compliance — {report.compliance_score:.2f} "
            f"({verdict(report.compliance_score)})**"
        )

    return "\n".join(lines)


def _print_execution_result(result: ExecutionResult, index: int) -> None:
    console.print(
        Panel(
            result.output,
            title=f"Generated Output #{index} — {result.policy_name}",
            border_style="green",
        )
    )


if __name__ == "__main__":
    app()
