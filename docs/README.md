# PolicyEval Documentation

Welcome to the PolicyEval documentation. Choose your path:

## Quick Links

- **New to PolicyEval?** Start with the [User Guide](GUIDE.md)
- **Quick Reference** → [Cheat Sheet](CHEATSHEET.md)
- **API Reference** → [API.md](API.md)
- **Real-world Examples** → [Use Cases](USECASES.md)
- **Common Questions** → [FAQ](FAQ.md)
- **Architecture & Design** → [ARCHITECTURE.md](ARCHITECTURE.md)
- **Contributing** → [../CONTRIBUTING.md](../CONTRIBUTING.md)

## Documentation Structure

### [User Guide](GUIDE.md)

Complete walkthrough for using PolicyEval:
- Core concepts (adherence, coverage, compliance)
- Basic usage examples
- Advanced features (programmatic evaluators, LiteLLM, custom judges)
- Testing patterns
- CI/CD integration
- Troubleshooting

**Start here** if you're using PolicyEval for the first time.

### [API Reference](API.md)

Comprehensive API documentation:
- Core classes (`Policy`, `Rule`, `PolicyTest`, `PolicyExecutor`)
- LLM abstraction (`LLM`, `LLMJudge`, `OpenAILLM`, `OpenAIJudge`)
- Report models (`PolicyReport`, `AdherenceReport`, `CoverageReport`)
- Utilities (`extract_rules`, `load_policy`, `assert_policy`)
- CLI commands (`run`, `execute`, `validate`)
- Scoring formulas

**Use this** when you need specific parameter details or method signatures.

### [Architecture](ARCHITECTURE.md)

Internal architecture and design decisions:
- System overview
- Module breakdown
- Data flow diagrams
- Design rationale (why generation and evaluation are separate, etc.)
- Extensibility points
- Testing strategy
- Performance considerations

**Read this** if you're contributing to PolicyEval or need to understand how it works under the hood.

### [Cheat Sheet](CHEATSHEET.md)

Quick reference for common tasks:
- Installation
- Basic evaluation and generation
- Pytest integration
- CLI commands
- Policy YAML format
- Cost optimization tips
- Common patterns

**Use this** for quick copy-paste code snippets.

### [Use Cases](USECASES.md)

Real-world applications across domains:
- Financial services (investment advice guardrails)
- Healthcare (HIPAA compliance)
- Legal (contract review)
- Insurance (claims processing)
- DevSecOps (security patch validation)
- Customer support (tone and escalation)
- Content moderation (community guidelines)
- Education (tutoring ethics)
- Code review (PR guidelines)

**Read this** to see how PolicyEval applies to your domain.

### [FAQ](FAQ.md)

Common questions and troubleshooting:
- General questions (what is PolicyEval, when to use it)
- Usage questions (cost reduction, LiteLLM, custom judges)
- Evaluation questions (adherence vs coverage, scoring formulas)
- Testing questions (pytest, CI/CD, thresholds)
- Integration questions (policy files, text extraction)

**Check this** when you hit a problem or have questions.

## Quick Examples

### Evaluate an LLM Output

```python
from policyeval import Policy, Rule, PolicyTest

policy = Policy(
    name="Financial Advice Safety",
    rules=[
        Rule(
            id="no_advice",
            description="Must not provide personalized investment advice",
            severity=1.0,
            adherence_type="binary",
        ),
    ],
)

test = PolicyTest(
    input="Should I buy Tesla stock?",
    output="I can't provide personalized investment advice. Please consult a financial advisor.",
    policy=policy,
)

report = test.run()
print(f"Compliance: {report.compliance_score:.2f}")
```

### Generate a Compliant Output

```python
from policyeval import PolicyExecutor

executor = PolicyExecutor(
    policy=policy,
    input="Should I buy Tesla stock?",
)

result = executor.run()
print(result.output)
```

### Use in Pytest

```python
from policyeval import assert_policy

def test_financial_advice():
    assert_policy(
        input="Should I buy Tesla stock?",
        output=bot_response,
        policy=policy,
        min_adherence=0.9,
        min_coverage=0.7,
    )
```

## Additional Resources

### Main README

The [main README](../README.md) contains:
- Installation instructions
- Quickstart example
- Key features list
- Links to examples
- CLI usage overview

### Examples

The [examples/](../examples/) directory has runnable examples:
- `insurance_claim.py` — Insurance policy compliance
- `legal_contract.py` — Legal contract term checking
- `healthcare_compliance.py` — HIPAA compliance
- `sca_remediation.py` — DevSecOps remediation policy evaluation
- `policy_execution.py` — Policy-guided generation

### Tests

The [tests/](../tests/) directory shows usage patterns:
- `test_engine.py` — Core evaluation and execution
- `test_metrics.py` — Adherence and coverage scoring
- `test_pytest_plugin.py` — Pytest integration
- `test_cli.py` — CLI usage

## Getting Help

- **Issues**: [GitHub Issues](https://github.com/Backline-AI/PolicyEval/issues)
- **Discussions**: [GitHub Discussions](https://github.com/Backline-AI/PolicyEval/discussions)
- **Email**: haggai.shachar@backline.ai

## Contributing

See [CONTRIBUTING.md](../CONTRIBUTING.md) for:
- Development setup
- Running tests
- Code quality tools
- Pull request process
- Adding examples

## License

PolicyEval is licensed under the MIT License. See [LICENSE](../LICENSE) for details.
