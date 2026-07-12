# PolicyEval User Guide

This guide walks you through using PolicyEval for policy compliance evaluation and policy-guided generation.

## Table of Contents

1. [Core Concepts](#core-concepts)
2. [Basic Usage](#basic-usage)
3. [Advanced Features](#advanced-features)
4. [Testing Patterns](#testing-patterns)
5. [CI/CD Integration](#cicd-integration)
6. [Troubleshooting](#troubleshooting)

---

## Core Concepts

### Two Dimensions of Compliance

PolicyEval evaluates outputs along two independent axes:

**Adherence**: Did the output follow the rules?
- Each rule gets a score (binary 0/1 or float 0–1)
- Weighted by user-defined severity
- Includes per-rule reasoning

**Coverage**: Did the output ONLY do what the rules say?
- Detects unexpected actions not covered by any rule
- Each uncovered action gets an LLM-determined severity
- Prevents "technically compliant but wrong" outputs

**Compliance**: A summary score combining both
- Weighted harmonic mean (penalises imbalance)
- Use for dashboards; use sub-reports for debugging

### Rule Types

**Binary rules** (hard constraints):
```python
Rule(
    id="no_medical_advice",
    description="Must never provide medical diagnoses",
    severity=1.0,
    adherence_type="binary",  # Pass/fail only
)
```

**Float rules** (soft constraints):
```python
Rule(
    id="friendly_tone",
    description="Should use a friendly, approachable tone",
    severity=0.5,
    adherence_type="float",  # Continuous 0–1 score
)
```

---

## Basic Usage

### 1. Define a Policy

```python
from policyeval import Policy, Rule

policy = Policy(
    name="Customer Support Policy",
    version="1.0",
    rules=[
        Rule(
            id="no_promises",
            description="Must not make promises about product features or timelines",
            severity=1.0,
            adherence_type="binary",
        ),
        Rule(
            id="empathy",
            description="Should acknowledge customer frustration empathetically",
            severity=0.6,
            adherence_type="float",
        ),
        Rule(
            id="escalation_path",
            description="Should provide a clear escalation path if unresolved",
            severity=0.7,
            adherence_type="float",
        ),
    ],
)
```

### 2. Evaluate an Output

```python
from policyeval import PolicyTest

test = PolicyTest(
    input="Why doesn't your app work on my phone? This is ridiculous!",
    output="I understand this is frustrating. Let me help troubleshoot. If we can't resolve it, I'll escalate to our engineering team.",
    policy=policy,
)

report = test.run()

print(f"Adherence : {report.adherence.score:.2f}")
print(f"Coverage  : {report.coverage.score:.2f}")
print(f"Compliance: {report.compliance_score:.2f}")

# Inspect failures
for r in report.adherence.rule_results:
    if not r.passed:
        print(f"❌ {r.rule_id}: {r.reasoning}")

# Check for unexpected actions
for ua in report.coverage.uncovered_actions:
    if ua.severity > 0.5:
        print(f"⚠️  UNCOVERED: {ua.description}")
```

### 3. Generate a Compliant Output

```python
from policyeval import PolicyExecutor

executor = PolicyExecutor(
    policy=policy,
    input="Why doesn't your app work on my phone?",
    system_prompt="You are a customer support agent.",
)

result = executor.run()
print(result.output)
```

### 4. Generate + Evaluate Loop

```python
# User-composed retry loop
for attempt in range(3):
    result = PolicyExecutor(policy=policy, input=user_query).run()
    
    report = PolicyTest(
        input=user_query,
        output=result.output,
        policy=policy,
    ).run()
    
    if report.compliance_score >= 0.9:
        print(f"✓ Compliant on attempt {attempt + 1}")
        break
    else:
        print(f"⚠ Attempt {attempt + 1} failed: {report.compliance_score:.2f}")
```

---

## Advanced Features

### Programmatic Evaluators

For deterministic checks (regex, version strings, keyword presence), skip the LLM:

```python
from policyeval import Rule, RuleResult

def check_api_key_leak(input: str, output: str, rule: Rule) -> RuleResult:
    import re
    api_key_pattern = r"sk-[a-zA-Z0-9]{32,}"
    found = re.search(api_key_pattern, output)
    
    return RuleResult(
        rule_id=rule.id,
        score=0.0 if found else 1.0,
        adherence_type="binary",
        severity=rule.severity,
        reasoning=f"API key {'LEAKED' if found else 'not found'} in output",
        source="programmatic",
    )

policy = Policy(
    name="Security Policy",
    rules=[
        Rule(
            id="no_api_keys",
            description="Must not expose API keys in responses",
            severity=1.0,
            adherence_type="binary",
            evaluator=check_api_key_leak,  # Programmatic check
        ),
        # Mix with LLM-evaluated rules
        Rule(
            id="no_credentials",
            description="Must not suggest sharing credentials",
            severity=1.0,
            adherence_type="binary",
            # No evaluator = LLM evaluation
        ),
    ],
)
```

### Independent Metrics

Save LLM calls by running only what you need:

```python
# Fast CI check: adherence only
report = test.run(metrics=["adherence"])
assert report.adherence.score >= 0.9

# Coverage only (no per-rule calls)
report = test.run(metrics=["coverage"])
assert len(report.coverage.uncovered_actions) == 0

# Both (default)
report = test.run()  # or test.run(metrics=["adherence", "coverage"])
```

### Batch vs Sequential Evaluation

**Batch mode** (default): Single LLM call evaluates all rules
- Faster, cheaper
- Good for most use cases

**Sequential mode**: One LLM call per rule
- More expensive
- More focused reasoning per rule
- Better for complex policies with many rules

```python
# Batch (default)
report = test.run()

# Sequential
test = PolicyTest(
    input=input,
    output=output,
    policy=policy,
    eval_mode="sequential",
)
report = test.run()
```

### Text-to-Rules Extraction

Convert unstructured requirements into a policy:

```python
from policyeval import extract_rules, Policy
from policyeval.llm import OpenAILLM

policy_text = """
1. Upgrade docker to v25.0.4 in go.mod
2. Update go.sum with new hashes
3. Replace ContainerJSON with InspectResponse
4. Add error handling for AuthenticationError
"""

rules = extract_rules(
    text=policy_text,
    llm=OpenAILLM(model="gpt-4o"),
    default_adherence_type="binary",
    default_severity=1.0,
)

policy = Policy(name="Docker Upgrade", rules=rules)

# Now evaluate a git diff against this policy
diff = get_git_diff()
report = PolicyTest(
    input=policy_text,
    output=diff,
    policy=policy,
).run()
```

### Using LiteLLM / Other Providers

#### For Generation (PolicyExecutor)

```python
from policyeval import PolicyExecutor
from policyeval.llm import OpenAILLM

# Anthropic via LiteLLM proxy
llm = OpenAILLM(
    model="anthropic/claude-3-opus",
    base_url="http://localhost:4000",
)

executor = PolicyExecutor(policy=policy, input="...", llm=llm)
result = executor.run()
```

#### For Evaluation (PolicyTest)

```python
from policyeval import PolicyTest
from policyeval.judges.openai_judge import OpenAIJudge

# Anthropic via LiteLLM proxy
judge = OpenAIJudge(
    model="anthropic/claude-3-opus",
    base_url="http://localhost:4000",
)

test = PolicyTest(
    input="...",
    output="...",
    policy=policy,
    judge=judge,
)
report = test.run()
```

### Custom Judge Implementation

Plug in any LLM:

```python
from policyeval.judges.base import LLMJudge
import anthropic

class ClaudeJudge(LLMJudge):
    def __init__(self, model: str = "claude-3-opus-20240229"):
        self.client = anthropic.Anthropic()
        self.model = model

    async def complete(self, system_prompt: str, prompt: str) -> str:
        response = self.client.messages.create(
            model=self.model,
            system=system_prompt,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text

    def complete_sync(self, system_prompt: str, prompt: str) -> str:
        import asyncio
        return asyncio.run(self.complete(system_prompt, prompt))

    async def evaluate(self, system_prompt: str, prompt: str) -> dict:
        import json
        text = await self.complete(system_prompt, prompt)
        return json.loads(text)

    def evaluate_sync(self, system_prompt: str, prompt: str) -> dict:
        import asyncio
        return asyncio.run(self.evaluate(system_prompt, prompt))

# Use it
test = PolicyTest(input="...", output="...", policy=policy, judge=ClaudeJudge())
report = test.run()
```

---

## Testing Patterns

### Pattern 1: Simple Adherence Check

```python
from policyeval import assert_policy, Policy, Rule

def test_no_medical_advice():
    policy = Policy(
        name="Healthcare Bot",
        rules=[
            Rule(
                id="no_diagnosis",
                description="Must not provide medical diagnoses",
                severity=1.0,
                adherence_type="binary",
            )
        ],
    )

    assert_policy(
        input="I have a headache. What's wrong with me?",
        output="I can't diagnose conditions. Please consult a doctor if symptoms persist.",
        policy=policy,
        min_adherence=1.0,  # Must pass perfectly
    )
```

### Pattern 2: Separate Thresholds

```python
def test_customer_support():
    policy = Policy(name="Support", rules=[...])
    
    assert_policy(
        input=user_query,
        output=bot_response,
        policy=policy,
        min_adherence=0.9,   # Strict adherence
        min_coverage=0.7,    # Allow some uncovered actions
    )
```

### Pattern 3: Check Specific Uncovered Actions

```python
def test_no_high_severity_uncovered():
    report = PolicyTest(input="...", output="...", policy=policy).run()
    
    # Allow low-severity uncovered actions, but not high-severity
    high_severity = [
        ua for ua in report.coverage.uncovered_actions
        if ua.severity > 0.8
    ]
    
    assert not high_severity, (
        f"High-severity uncovered actions: "
        + ", ".join(ua.description for ua in high_severity)
    )
```

### Pattern 4: Adherence-Only CI

Fast checks for CI pipelines:

```python
def test_critical_rules_only():
    """Only check hard constraints in CI; full evaluation nightly."""
    assert_policy(
        input=query,
        output=response,
        policy=policy,
        metrics=["adherence"],  # Skip coverage for speed
        min_score=1.0,          # All binary rules must pass
    )
```

### Pattern 5: Parametrized Tests

```python
import pytest

test_cases = [
    ("How do I reset my password?", "Click 'Forgot Password' on the login page."),
    ("Why is my account locked?", "Your account may be locked after multiple failed login attempts."),
    ("Can you delete my data?", "Yes, we can process a data deletion request. Please contact privacy@example.com."),
]

@pytest.mark.parametrize("input,output", test_cases)
def test_support_responses(input, output):
    assert_policy(
        input=input,
        output=output,
        policy=support_plan,
        min_compliance=0.85,
    )
```

---

## CI/CD Integration

### GitHub Actions

```yaml
name: Policy Compliance Tests

on: [push, pull_request]

jobs:
  policy-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - uses: astral-sh/setup-uv@v4
      
      - name: Install dependencies
        run: uv sync --dev
      
      - name: Run policy tests
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
        run: |
          uv run pytest tests/test_plan_compliance.py \
            --policyeval-model gpt-4o-mini \
            -v
      
      - name: Upload policy report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: policy-report
          path: policy-report.json
```

### GitLab CI

```yaml
policy-tests:
  image: python:3.11
  before_script:
    - pip install uv
    - uv sync --dev
  script:
    - uv run pytest tests/test_plan_compliance.py --policyeval-model gpt-4o-mini -v
  artifacts:
    when: always
    paths:
      - policy-report.json
```

### Pre-commit Hook

`.pre-commit-config.yaml`:
```yaml
repos:
  - repo: local
    hooks:
      - id: policy-compliance
        name: Policy Compliance
        entry: uv run pytest tests/test_critical_plans.py -x
        language: system
        pass_filenames: false
```

### Makefile Integration

```makefile
.PHONY: test-policy
test-policy:
	uv run pytest tests/test_plan_compliance.py -v

.PHONY: test-policy-fast
test-policy-fast:
	uv run pytest tests/test_plan_compliance.py \
		--policyeval-model gpt-4o-mini \
		-k "not slow"
```

---

## Troubleshooting

### Issue: LLM returns inconsistent scores

**Symptom**: Same input/output gets different scores on repeated runs.

**Solutions**:
1. Use `eval_mode="sequential"` for more consistent per-rule evaluation
2. Make rule descriptions more specific and objective
3. `OpenAIJudge` already defaults to `temperature=0`; residual inconsistency at that point comes from the model itself, not a tunable setting

### Issue: Coverage reports too many false positives

**Symptom**: Coverage score is low due to harmless uncovered actions.

**Solutions**:
1. Add more rules to the policy to increase coverage
2. Use separate thresholds: strict adherence, lenient coverage
3. Filter out low-severity uncovered actions in tests:
   ```python
   critical_uncovered = [
       ua for ua in report.coverage.uncovered_actions
       if ua.severity > 0.7
   ]
   assert not critical_uncovered
   ```

### Issue: Adherence score unexpectedly low

**Symptom**: Overall adherence is low but most rules pass.

**Cause**: One high-severity rule failing, or a binary rule failing (floors to 0).

**Debug**:
```python
for r in report.adherence.rule_results:
    print(f"{r.rule_id}: score={r.score:.2f}, severity={r.severity:.2f}")
    if not r.passed:
        print(f"  ❌ {r.reasoning}")
```

### Issue: Programmatic evaluator not running

**Symptom**: Rule with `evaluator` still calls LLM.

**Check**:
1. Evaluator function signature matches:
   ```python
   def evaluator(input: str, output: str, rule: Rule) -> RuleResult:
   ```
2. Function is passed to `Rule(evaluator=your_function)`
3. Function returns a `RuleResult` object (not just a score)

### Issue: Tests fail in CI but pass locally

**Common causes**:
1. Different models: CI may use `gpt-4o-mini`, local uses `gpt-4o`
   - Solution: Pin model in tests or use CLI flag consistently
2. Missing `OPENAI_API_KEY` in CI
   - Solution: Add to GitHub Secrets / GitLab Variables
3. Flaky LLM responses
   - Solution: Use programmatic evaluators for critical rules

### Issue: Slow test suite

**Optimizations**:
1. Run adherence-only in fast CI; full evaluation nightly
2. Use `gpt-4o-mini` instead of `gpt-4o` for tests
3. Cache evaluation results for fixed test cases
4. Use programmatic evaluators where possible (no LLM call)
5. Run coverage-only when you only care about unexpected actions

### Issue: High LLM API costs

**Cost reduction strategies**:
1. Use `metrics=["adherence"]` for CI checks
2. Switch to `gpt-4o-mini` (95% cheaper than `gpt-4o`)
3. Use programmatic evaluators for deterministic rules
4. Run full evaluations only on main branch / nightly
5. Route through LiteLLM with caching enabled

---

## Best Practices

### Writing Good Rules

✅ **Good**: Specific, objective, actionable
```python
Rule(
    id="version_check",
    description="Upgrade github.com/docker/docker to exactly v25.0.4 in go.mod",
    adherence_type="binary",
)
```

❌ **Bad**: Vague, subjective
```python
Rule(
    id="good_code",
    description="Code should be good quality",
    adherence_type="float",
)
```

### Severity Guidelines

- **1.0**: Critical, regulatory, security-sensitive
- **0.7–0.9**: Important for correctness but not critical
- **0.4–0.6**: Nice-to-have, style, tone
- **0.0–0.3**: Optional suggestions

### When to Use Binary vs Float

Use **binary** for:
- Regulatory requirements
- Security constraints
- Must-never / must-always rules
- Programmatic checks (version strings, regex)

Use **float** for:
- Tone, style, quality
- "Should usually" constraints
- Degree-of-compliance scenarios

### Monitoring and Observability

Track these metrics over time:
```python
report = test.run()

# Log for monitoring
print(f"adherence={report.adherence.score:.3f}")
print(f"coverage={report.coverage.score:.3f}")
print(f"compliance={report.compliance_score:.3f}")
print(f"n_uncovered={len(report.coverage.uncovered_actions)}")
print(f"n_failed_rules={sum(1 for r in report.adherence.rule_results if not r.passed)}")
```

Graph these in your observability platform to detect:
- Degrading adherence over time
- Spikes in uncovered actions
- Correlation with model updates
