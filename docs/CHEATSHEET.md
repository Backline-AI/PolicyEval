# PolicyEval Cheat Sheet

Quick reference for common tasks.

## Installation

```bash
pip install policyeval
export OPENAI_API_KEY=sk-...
```

## Basic Evaluation

```python
from policyeval import Policy, Rule, PolicyTest

# Define policy
policy = Policy(
    name="My Policy",
    rules=[
        Rule(id="R1", description="Must not do X", severity=1.0, adherence_type="binary"),
        Rule(id="R2", description="Should include Y", severity=0.7, adherence_type="float"),
    ],
)

# Evaluate
test = PolicyTest(input="query", output="response", policy=policy)
report = test.run()

# Check results
print(f"Adherence: {report.adherence.score:.2f}")
print(f"Coverage: {report.coverage.score:.2f}")
print(f"Compliance: {report.compliance_score:.2f}")
```

## Generation

```python
from policyeval import PolicyExecutor

executor = PolicyExecutor(policy=policy, input="user query")
result = executor.run()
print(result.output)
```

## Pytest Integration

```python
from policyeval import assert_policy

def test_compliance():
    assert_policy(
        input="query",
        output=bot_response,
        policy=policy,
        min_adherence=0.9,
        min_coverage=0.7,
    )
```

```bash
pytest --policyeval-model gpt-4o-mini
```

## CLI Usage

```bash
# Extract a policy from plain text
policyeval extract policy.md -o policy.yaml

# Evaluate
policyeval run policy.yaml interactions.json

# Evaluate, printing the report as markdown or json
policyeval run policy.yaml interactions.json --format markdown
policyeval run policy.yaml interactions.json --format json

# Generate
policyeval execute policy.yaml --input "query"

# Validate
policyeval validate policy.yaml
```

## Policy YAML

```yaml
name: My Policy
version: "1.0"
rules:
  - id: no_advice
    description: Must not provide personalized advice
    severity: 1.0
    adherence_type: binary
  - id: friendly
    description: Should use friendly tone
    severity: 0.5
    adherence_type: float
```

## Load Policy

```python
from policyeval.policy.loader import load_policy

policy = load_policy("policy.yaml")
```

## Programmatic Evaluator

```python
from policyeval import Rule, RuleResult

def check_version(input: str, output: str, rule: Rule) -> RuleResult:
    found = "v25.0.4" in output
    return RuleResult(
        rule_id=rule.id,
        score=1.0 if found else 0.0,
        adherence_type="binary",
        severity=rule.severity,
        reasoning=f"Version {'found' if found else 'not found'}",
        source="programmatic",
    )

Rule(id="version", description="...", evaluator=check_version)
```

## Independent Metrics

```python
# Adherence only (faster)
report = test.run(metrics=["adherence"])

# Coverage only
report = test.run(metrics=["coverage"])

# Both (default)
report = test.run()
```

## LiteLLM / Other Providers

```python
from policyeval.llm import OpenAILLM
from policyeval.judges.openai_judge import OpenAIJudge

# Generation via LiteLLM
llm = OpenAILLM(model="anthropic/claude-3-opus", base_url="http://localhost:4000")
executor = PolicyExecutor(policy=policy, input="...", llm=llm)

# Evaluation via LiteLLM
judge = OpenAIJudge(model="anthropic/claude-3-opus", base_url="http://localhost:4000")
test = PolicyTest(input="...", output="...", policy=policy, judge=judge)
```

## Extract Rules from Text

```python
from policyeval import extract_rules, Policy
from policyeval.llm import OpenAILLM

text = "1. Upgrade docker\n2. Add tests"
rules = extract_rules(text, llm=OpenAILLM(model="gpt-4o"))
policy = Policy(name="Policy", rules=rules)
```

## Sequential Evaluation

```python
# One LLM call per rule (more focused)
test = PolicyTest(input="...", output="...", policy=policy, eval_mode="sequential")
```

## Inspect Failures

```python
report = test.run()

# Check failed rules
for r in report.adherence.rule_results:
    if not r.passed:
        print(f"❌ {r.rule_id}: {r.reasoning}")

# Check high-severity uncovered actions
for ua in report.coverage.uncovered_actions:
    if ua.severity > 0.7:
        print(f"⚠️ {ua.description}")
```

## Generate + Evaluate Loop

```python
for attempt in range(3):
    result = PolicyExecutor(policy=policy, input=query).run()
    report = PolicyTest(input=query, output=result.output, policy=policy).run()
    
    if report.compliance_score >= 0.9:
        print(f"✓ Success on attempt {attempt + 1}")
        break
```

## CI/CD (GitHub Actions)

```yaml
- name: Policy tests
  env:
    OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
  run: |
    uv run pytest tests/test_plan_compliance.py \
      --policyeval-model gpt-4o-mini
```

## Async API

```python
# Async evaluation
report = await test.arun()

# Async generation
result = await executor.arun()

# Concurrent evaluations
reports = await asyncio.gather(*[test.arun() for test in tests])
```

## Report Serialization

```python
# To dict / JSON (pydantic)
data = report.model_dump(mode="json")
json_str = report.model_dump_json(indent=2)

# From dict
from policyeval.reporting.models import PolicyReport
report = PolicyReport.model_validate(data)
```

## Cost Optimization

1. Use `gpt-4o-mini` instead of `gpt-4o`
2. Run adherence-only: `test.run(metrics=["adherence"])`
3. Use programmatic evaluators (no LLM call)
4. Batch mode (default) instead of sequential
5. Route through LiteLLM with caching

## Debugging

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Then run your code — logs will show LLM prompts/responses
```

## Common Patterns

### Separate Thresholds
```python
assert report.adherence.score >= 0.90
assert report.coverage.score >= 0.70
```

### Filter Uncovered Actions
```python
critical = [ua for ua in report.coverage.uncovered_actions if ua.severity > 0.7]
assert not critical, "High-severity uncovered actions found"
```

### Parametrized Tests
```python
@pytest.mark.parametrize("input,output", test_cases)
def test_cases(input, output):
    assert_policy(input=input, output=output, policy=policy, min_compliance=0.85)
```

## Model IDs

| Provider | Model ID | Notes |
|----------|----------|-------|
| OpenAI | `gpt-4o` | Most capable |
| OpenAI | `gpt-4o-mini` | 95% cheaper |
| Anthropic (via LiteLLM) | `anthropic/claude-3-opus` | Requires LiteLLM proxy |
| Anthropic (via LiteLLM) | `anthropic/claude-3-sonnet` | Fast, capable |
| Azure | `gpt-4` | Set `base_url` to Azure endpoint |

## Quick Links

- [Full Guide](GUIDE.md)
- [API Reference](API.md)
- [FAQ](FAQ.md)
- [Examples](../examples/)
