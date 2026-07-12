"""Tests for the Typer CLI."""

import json

import yaml
from typer.testing import CliRunner

import policyeval.cli.main as cli_main
from policyeval.cli.main import app
from policyeval.policy.loader import load_policy
from policyeval.policy.models import Rule
from policyeval.reporting.models import (
    AdherenceReport,
    CoverageReport,
    ExecutionResult,
    PolicyReport,
    RuleResult,
)

runner = CliRunner()


SAMPLE_POLICY = {
    "name": "Test Policy",
    "version": "1.0",
    "rules": [
        {
            "id": "R1",
            "description": "Must not do bad things",
            "severity": 1.0,
            "adherence_type": "binary",
        },
    ],
}

SAMPLE_OUTPUTS = [{"input": "What should I do?", "output": "Do good things."}]


class TestValidateCommand:
    def test_valid_policy(self, tmp_path):
        f = tmp_path / "policy.yaml"
        f.write_text(yaml.dump(SAMPLE_POLICY))
        result = runner.invoke(app, ["validate", str(f)])
        assert result.exit_code == 0
        assert "Valid" in result.output

    def test_missing_file(self, tmp_path):
        result = runner.invoke(app, ["validate", str(tmp_path / "missing.yaml")])
        assert result.exit_code == 1

    def test_invalid_yaml(self, tmp_path):
        f = tmp_path / "policy.yaml"
        f.write_text(yaml.dump({"name": "No rules"}))
        result = runner.invoke(app, ["validate", str(f)])
        assert result.exit_code == 1


class TestRunCommandFileValidation:
    def test_missing_policy_file(self, tmp_path):
        outputs_file = tmp_path / "outputs.json"
        outputs_file.write_text(json.dumps(SAMPLE_OUTPUTS))
        result = runner.invoke(
            app, ["run", str(tmp_path / "missing.yaml"), str(outputs_file)]
        )
        assert result.exit_code == 1
        assert "not found" in result.output.lower() or "Error" in result.output

    def test_missing_outputs_file(self, tmp_path):
        policy_file = tmp_path / "policy.yaml"
        policy_file.write_text(yaml.dump(SAMPLE_POLICY))
        result = runner.invoke(
            app, ["run", str(policy_file), str(tmp_path / "missing.json")]
        )
        assert result.exit_code == 1

    def test_invalid_interactions_format(self, tmp_path):
        # A bare scalar is neither a single interaction object nor an array.
        policy_file = tmp_path / "policy.yaml"
        policy_file.write_text(yaml.dump(SAMPLE_POLICY))
        interactions_file = tmp_path / "interactions.json"
        interactions_file.write_text(json.dumps("just a string"))
        result = runner.invoke(app, ["run", str(policy_file), str(interactions_file)])
        assert result.exit_code == 1
        assert "object or array" in result.output.lower()


def _fake_report() -> PolicyReport:
    return PolicyReport(
        adherence=AdherenceReport(
            score=0.9,
            reasoning="Mostly compliant.",
            rule_results=[
                RuleResult(
                    rule_id="R1",
                    score=1.0,
                    adherence_type="binary",
                    severity=1.0,
                    reasoning="Passed.",
                )
            ],
        ),
        coverage=CoverageReport(score=1.0, reasoning="All covered."),
        compliance_score=0.95,
    )


class TestRunCommandSuccess:
    def _write_inputs(self, tmp_path):
        policy_file = tmp_path / "policy.yaml"
        policy_file.write_text(yaml.dump(SAMPLE_POLICY))
        outputs_file = tmp_path / "outputs.json"
        outputs_file.write_text(json.dumps(SAMPLE_OUTPUTS))
        return policy_file, outputs_file

    def test_run_prints_report(self, tmp_path, monkeypatch):
        policy_file, outputs_file = self._write_inputs(tmp_path)
        monkeypatch.setattr(
            cli_main.EvaluationEngine,
            "evaluate",
            lambda self, *a, **k: _fake_report(),
        )
        result = runner.invoke(app, ["run", str(policy_file), str(outputs_file)])
        assert result.exit_code == 0
        assert "Adherence" in result.output
        assert "Compliance" in result.output

    def test_run_accepts_single_interaction_object(self, tmp_path, monkeypatch):
        # A single {input, output} object is treated as a batch of one.
        policy_file = tmp_path / "policy.yaml"
        policy_file.write_text(yaml.dump(SAMPLE_POLICY))
        interactions_file = tmp_path / "interaction.json"
        interactions_file.write_text(
            json.dumps({"input": "What should I do?", "output": "Do good things."})
        )
        monkeypatch.setattr(
            cli_main.EvaluationEngine,
            "evaluate",
            lambda self, *a, **k: _fake_report(),
        )
        result = runner.invoke(app, ["run", str(policy_file), str(interactions_file)])
        assert result.exit_code == 0
        assert "Evaluating item 1/1" in result.output
        assert "Compliance" in result.output

    def test_run_accepts_yaml_interactions_file(self, tmp_path, monkeypatch):
        policy_file = tmp_path / "policy.yaml"
        policy_file.write_text(yaml.dump(SAMPLE_POLICY))
        interaction_file = tmp_path / "interaction.yaml"
        interaction_file.write_text(
            yaml.dump({"input": "What should I do?", "output": "Do good things."})
        )
        monkeypatch.setattr(
            cli_main.EvaluationEngine,
            "evaluate",
            lambda self, *a, **k: _fake_report(),
        )
        result = runner.invoke(app, ["run", str(policy_file), str(interaction_file)])
        assert result.exit_code == 0
        assert "Evaluating item 1/1" in result.output
        assert "Compliance" in result.output

    def test_run_saves_report_to_file(self, tmp_path, monkeypatch):
        policy_file, outputs_file = self._write_inputs(tmp_path)
        report_file = tmp_path / "report.json"
        monkeypatch.setattr(
            cli_main.EvaluationEngine,
            "evaluate",
            lambda self, *a, **k: _fake_report(),
        )
        result = runner.invoke(
            app,
            ["run", str(policy_file), str(outputs_file), "-o", str(report_file)],
        )
        assert result.exit_code == 0
        assert report_file.exists()
        saved = json.loads(report_file.read_text())
        assert saved[0]["compliance_score"] == 0.95

    def test_run_saves_markdown_to_file(self, tmp_path, monkeypatch):
        policy_file, outputs_file = self._write_inputs(tmp_path)
        report_file = tmp_path / "result.md"
        monkeypatch.setattr(
            cli_main.EvaluationEngine,
            "evaluate",
            lambda self, *a, **k: _fake_report(),
        )
        result = runner.invoke(
            app,
            [
                "run",
                str(policy_file),
                str(outputs_file),
                "--format",
                "markdown",
                "-o",
                str(report_file),
            ],
        )
        assert result.exit_code == 0
        assert report_file.exists()
        saved = report_file.read_text()
        assert "### Result #1" in saved
        assert "`R1`" in saved
        assert "| ---" not in saved

    def test_run_adherence_only_metric(self, tmp_path, monkeypatch):
        policy_file, outputs_file = self._write_inputs(tmp_path)
        captured = {}

        def fake_eval(self, input_text, output_text, policy, **kwargs):
            captured["metrics"] = kwargs.get("metrics")
            return _fake_report()

        monkeypatch.setattr(cli_main.EvaluationEngine, "evaluate", fake_eval)
        result = runner.invoke(
            app,
            ["run", str(policy_file), str(outputs_file), "--metrics", "adherence"],
        )
        assert result.exit_code == 0
        assert captured["metrics"] == ["adherence"]

    def test_run_skips_non_dict_items(self, tmp_path, monkeypatch):
        policy_file = tmp_path / "policy.yaml"
        policy_file.write_text(yaml.dump(SAMPLE_POLICY))
        outputs_file = tmp_path / "outputs.json"
        outputs_file.write_text(
            json.dumps(["not a dict", {"input": "x", "output": "y"}])
        )
        monkeypatch.setattr(
            cli_main.EvaluationEngine,
            "evaluate",
            lambda self, *a, **k: _fake_report(),
        )
        result = runner.invoke(app, ["run", str(policy_file), str(outputs_file)])
        assert result.exit_code == 0
        assert "Skipping" in result.output

    def test_run_format_markdown(self, tmp_path, monkeypatch):
        policy_file, outputs_file = self._write_inputs(tmp_path)
        monkeypatch.setattr(
            cli_main.EvaluationEngine,
            "evaluate",
            lambda self, *a, **k: _fake_report(),
        )
        result = runner.invoke(
            app,
            ["run", str(policy_file), str(outputs_file), "--format", "markdown"],
        )
        assert result.exit_code == 0
        assert "### Result #1" in result.output
        assert "**Adherence" in result.output
        assert "`R1`" in result.output
        # The report must not fall back to a Markdown table.
        assert "| ---" not in result.output

    def test_run_threshold_flips_verdict(self, tmp_path, monkeypatch):
        # _fake_report has coverage 1.0 / compliance 0.95 but adherence 0.9;
        # a 0.92 threshold should fail adherence while passing coverage.
        policy_file, outputs_file = self._write_inputs(tmp_path)
        monkeypatch.setattr(
            cli_main.EvaluationEngine,
            "evaluate",
            lambda self, *a, **k: _fake_report(),
        )
        result = runner.invoke(
            app,
            [
                "run",
                str(policy_file),
                str(outputs_file),
                "--format",
                "markdown",
                "--threshold",
                "0.92",
            ],
        )
        assert result.exit_code == 0
        assert "**Adherence — 0.90 (FAIL)**" in result.output
        assert "**Coverage — 1.00 (PASS)**" in result.output

    def test_run_format_json(self, tmp_path, monkeypatch):
        policy_file, outputs_file = self._write_inputs(tmp_path)
        monkeypatch.setattr(
            cli_main.EvaluationEngine,
            "evaluate",
            lambda self, *a, **k: _fake_report(),
        )
        # CliRunner keeps stdout/stderr separate, so stdout is clean JSON
        # while progress messages land on stderr.
        result = runner.invoke(
            app,
            ["run", str(policy_file), str(outputs_file), "-f", "json"],
        )
        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert isinstance(payload, list)
        assert payload[0]["compliance_score"] == 0.95

    def test_run_evaluation_error_exits(self, tmp_path, monkeypatch):
        policy_file, outputs_file = self._write_inputs(tmp_path)

        def boom(self, *a, **k):
            raise RuntimeError("judge exploded")

        monkeypatch.setattr(cli_main.EvaluationEngine, "evaluate", boom)
        result = runner.invoke(app, ["run", str(policy_file), str(outputs_file)])
        assert result.exit_code == 1

    def test_run_prints_violations_and_uncovered(self, tmp_path, monkeypatch):
        policy_file, outputs_file = self._write_inputs(tmp_path)
        failing = PolicyReport(
            adherence=AdherenceReport(
                score=0.0,
                reasoning="Failed hard.",
                rule_results=[
                    RuleResult(
                        rule_id="R1",
                        score=0.0,
                        adherence_type="binary",
                        severity=1.0,
                        reasoning="Recommended a specific stock.",
                    )
                ],
            ),
            coverage=CoverageReport(
                score=0.4,
                reasoning="Unexpected behavior.",
                uncovered_actions=[
                    {
                        "description": "Promised guaranteed returns",
                        "severity": 0.9,
                        "reasoning": "No rule covers this",
                    }
                ],
            ),
            compliance_score=0.2,
        )
        monkeypatch.setattr(
            cli_main.EvaluationEngine, "evaluate", lambda self, *a, **k: failing
        )
        result = runner.invoke(app, ["run", str(policy_file), str(outputs_file)])
        assert result.exit_code == 0
        assert "FAIL" in result.output
        assert "R1" in result.output


class TestExecuteCommand:
    def test_execute_single_input(self, tmp_path, monkeypatch):
        policy_file = tmp_path / "policy.yaml"
        policy_file.write_text(yaml.dump(SAMPLE_POLICY))
        monkeypatch.setattr(
            cli_main.ExecutionEngine,
            "execute_sync",
            lambda self, input_text, policy: ExecutionResult(
                output="Generated answer.", policy_name=policy.name
            ),
        )
        result = runner.invoke(
            app, ["execute", str(policy_file), "--input", "Should I buy Tesla?"]
        )
        assert result.exit_code == 0
        assert "Generated answer." in result.output

    def test_execute_requires_input_or_file(self, tmp_path):
        policy_file = tmp_path / "policy.yaml"
        policy_file.write_text(yaml.dump(SAMPLE_POLICY))
        result = runner.invoke(app, ["execute", str(policy_file)])
        assert result.exit_code == 1
        assert "either --input" in result.output.lower()

    def test_execute_missing_policy(self, tmp_path):
        result = runner.invoke(
            app, ["execute", str(tmp_path / "missing.yaml"), "--input", "q"]
        )
        assert result.exit_code == 1

    def test_execute_batch_from_file(self, tmp_path, monkeypatch):
        policy_file = tmp_path / "policy.yaml"
        policy_file.write_text(yaml.dump(SAMPLE_POLICY))
        inputs_file = tmp_path / "inputs.json"
        inputs_file.write_text(json.dumps([{"input": "q1"}, "q2"]))
        results_file = tmp_path / "results.json"
        monkeypatch.setattr(
            cli_main.ExecutionEngine,
            "execute_sync",
            lambda self, input_text, policy: ExecutionResult(
                output=f"answer to {input_text}", policy_name=policy.name
            ),
        )
        result = runner.invoke(
            app,
            ["execute", str(policy_file), str(inputs_file), "-o", str(results_file)],
        )
        assert result.exit_code == 0
        assert results_file.exists()
        saved = json.loads(results_file.read_text())
        assert len(saved) == 2

    def test_execute_missing_inputs_file(self, tmp_path):
        policy_file = tmp_path / "policy.yaml"
        policy_file.write_text(yaml.dump(SAMPLE_POLICY))
        result = runner.invoke(
            app, ["execute", str(policy_file), str(tmp_path / "missing.json")]
        )
        assert result.exit_code == 1


class TestExtractCommand:
    def _fake_rules(self):
        return [
            Rule(
                id="no_advice",
                description="Must not give advice",
                severity=1.0,
                adherence_type="binary",
            ),
            Rule(
                id="disclaimer",
                description="Should include a disclaimer",
                severity=0.7,
                adherence_type="float",
                scope="investment queries",
            ),
        ]

    def test_extract_to_stdout(self, tmp_path, monkeypatch):
        md = tmp_path / "policy.md"
        md.write_text("- No advice\n- Include a disclaimer\n")
        monkeypatch.setattr(
            cli_main, "extract_rules", lambda **kwargs: self._fake_rules()
        )
        result = runner.invoke(app, ["extract", str(md)])
        assert result.exit_code == 0
        assert "no_advice" in result.output
        assert "adherence_type: binary" in result.output

    def test_extract_to_file_and_reload(self, tmp_path, monkeypatch):
        md = tmp_path / "policy.md"
        md.write_text("- No advice\n- Include a disclaimer\n")
        out = tmp_path / "policy.yaml"
        monkeypatch.setattr(
            cli_main, "extract_rules", lambda **kwargs: self._fake_rules()
        )
        result = runner.invoke(
            app, ["extract", str(md), "-o", str(out), "-n", "My Policy"]
        )
        assert result.exit_code == 0
        assert out.exists()
        # Generated YAML must round-trip through the loader.
        reloaded = load_policy(out)
        assert reloaded.name == "My Policy"
        assert len(reloaded.rules) == 2
        assert reloaded.rules[1].scope == "investment queries"

    def test_extract_defaults_name_to_file_stem(self, tmp_path, monkeypatch):
        md = tmp_path / "financial_advice.md"
        md.write_text("- No advice\n")
        out = tmp_path / "out.yaml"
        monkeypatch.setattr(
            cli_main, "extract_rules", lambda **kwargs: self._fake_rules()
        )
        result = runner.invoke(app, ["extract", str(md), "-o", str(out)])
        assert result.exit_code == 0
        assert load_policy(out).name == "financial_advice"

    def test_extract_missing_file(self, tmp_path):
        result = runner.invoke(app, ["extract", str(tmp_path / "missing.md")])
        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    def test_extract_empty_file(self, tmp_path):
        md = tmp_path / "empty.md"
        md.write_text("   \n")
        result = runner.invoke(app, ["extract", str(md)])
        assert result.exit_code == 1
        assert "empty" in result.output.lower()

    def test_extract_failure_exits(self, tmp_path, monkeypatch):
        md = tmp_path / "policy.md"
        md.write_text("- No advice\n")

        def boom(**kwargs):
            raise ValueError("extractor exploded")

        monkeypatch.setattr(cli_main, "extract_rules", boom)
        result = runner.invoke(app, ["extract", str(md)])
        assert result.exit_code == 1
        assert "failed" in result.output.lower()
