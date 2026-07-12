# Frequently Asked Questions

## General

### What is PolicyEval?

PolicyEval is a framework for evaluating LLM outputs against policies and generating policy-compliant responses. It measures two dimensions:
- **Adherence**: Did the output follow the rules?
- **Coverage**: Did the output ONLY do what the rules say?

### When should I use PolicyEval?

Use PolicyEval when you need to:
- Enforce compliance policies on LLM outputs (legal, regulatory, safety)
- Validate that an LLM followed a policy or contract
- Generate responses that comply with domain constraints
- Test LLM behavior against expected guidelines
- Audit LLM outputs for unexpected actions

### How is this different from other LLM evaluation frameworks?

PolicyEval is policy-centric, not benchmark-centric:
- **Not a benchmark**: No predefined metrics like BLEU or ROUGE
- **User-defined rules**: You specify what compliance means
- **Two-dimensional**: Adherence (rule-following) + Coverage (unexpected actions)
- **Generation + Evaluation**: Both generate compliant outputs and evaluate existing ones
- **Domain-agnostic**: Works for legal, healthcare, finance, DevSecOps, etc.

### Does PolicyEval require fine-tuning or training?

No. PolicyEval uses an "LLM-as-a-judge" approach — no training required. You just:
1. Define your policy (rules)
2. Pass it an LLM output to evaluate
3. Get back structured scores and reasoning

## Usage

### Can I use PolicyEval with models other than OpenAI?

Yes! PolicyEval supports any OpenAI-compatible endpoint via `base_url`:

**Anthropic via LiteLLM:**
```python
from policyeval.llm import OpenAILLM

llm = OpenAILLM(
    model="anthropic/claude-3-opus",
    base_url="http://localhost:4000",  # LiteLLM proxy
)
```

**Custom judge:**
```python
from policyeval.judges.base import LLMJudge

class MyJudge(LLMJudge):
    # Implement complete(), evaluate(), etc.
    pass
```

See [Custom Judge Implementation](GUIDE.md#custom-judge-implementation) for details.

### What's the difference between `PolicyTest` and `PolicyExecutor`?

- **`PolicyTest`**: Evaluates an existing output against a policy
  - Input: policy + input + output (already generated)
  - Output: `PolicyReport` with adherence/coverage scores

- **`PolicyExecutor`**: Generates a new output that tries to follow the policy
  - Input: policy + input (no output yet)
  - Output: `ExecutionResult` with generated text

They're separate operations — compose them yourself:
```python
result = PolicyExecutor(policy=policy, input=query).run()
report = PolicyTest(input=query, output=result.output, policy=policy).run()
```

### When should I use batch vs sequential evaluation?

**Batch mode** (default):
- Single LLM call evaluates all rules at once
- Faster, cheaper
- Good for most policies

**Sequential mode**:
- One LLM call per rule
- More focused reasoning per rule
- Better for complex policies with many rules (10+)
- Use when batch mode gives inconsistent results

```python
test = PolicyTest(..., eval_mode="sequential")
```

### How do I reduce LLM API costs?

1. **Use `gpt-4o-mini`** instead of `gpt-4o` (95% cheaper)
2. **Run adherence-only** for fast CI checks: `test.run(metrics=["adherence"])`
3. **Use programmatic evaluators** for deterministic rules (no LLM call)
4. **Batch mode** instead of sequential (1 call vs N calls)
5. **Route through LiteLLM** with caching enabled
6. **Run full evaluations only on main branch** / nightly

### Can I mix programmatic and LLM-evaluated rules?

Yes! Rules with an `evaluator` function skip the LLM entirely:

```python
def check_version(input: str, output: str, rule: Rule) -> RuleResult:
    found = "v25.0.4" in output
    return RuleResult(
        rule_id=rule.id,
        score=1.0 if found else 0.0,
        adherence_type="binary",
        severity=rule.severity,
        reasoning=f"v25.0.4 {'found' if 'not found'} in output",
        source="programmatic",
    )

policy = Policy(
    name="Upgrade Policy",
    rules=[
        Rule(id="version", evaluator=check_version),  # Programmatic
        Rule(id="tests", description="Must add tests"),  # LLM-evaluated
    ],
)
```

## Evaluation

### What does adherence measure?

Adherence measures **rule compliance**: did the output follow each rule in the policy?

- Each rule gets a score (0.0–1.0)
- Weighted by user-defined severity
- Binary rules (pass/fail) or float rules (continuous)
- Overall adherence = weighted average
- If **any** binary rule fails, adherence = 0 (fail-fast)

### What does coverage measure?

Coverage measures **unexpected actions**: did the output do things not covered by any rule?

- LLM scans output for actions/changes/behaviors
- Checks if each action is covered by a policy rule
- Uncovered actions get an LLM-determined severity (0.0–1.0)
- Coverage score = 1.0 - (sum of uncovered severities / n_actions)

High adherence + low coverage = follows rules but does unexpected things.

### What's the compliance score?

Compliance is a **summary metric** combining adherence and coverage:
- Weighted harmonic mean (penalizes imbalance)
- Arithmetic mean fallback if either metric is 0

**Don't rely on compliance alone.** Use adherence and coverage sub-reports for debugging and gates.

### Why is my adherence score 0 when most rules pass?

One of two reasons:

1. **A binary rule failed** — Binary rule failure floors adherence to 0 (fail-fast semantics)
2. **High-severity rule failed** — A rule with `severity=1.0` failing heavily impacts the weighted average

Debug:
```python
for r in report.adherence.rule_results:
    print(f"{r.rule_id}: score={r.score:.2f}, severity={r.severity:.2f}")
    if not r.passed:
        print(f"  ❌ {r.reasoning}")
```

### Why does coverage report false positives?

Coverage reports actions **not covered by any rule**. If your policy is sparse, coverage will be low.

Solutions:
1. **Add more rules** to increase coverage
2. **Use separate thresholds**: strict adherence, lenient coverage
3. **Filter high-severity only**:
   ```python
   critical = [ua for ua in report.coverage.uncovered_actions if ua.severity > 0.7]
   assert not critical
   ```

### Can I get just adherence or just coverage?

Yes! Save LLM calls by running only what you need:

```python
# Adherence only (no coverage call)
report = test.run(metrics=["adherence"])

# Coverage only (no per-rule adherence calls)
report = test.run(metrics=["coverage"])

# Both (default)
report = test.run()
```

## Rules

### Should I use binary or float rules?

**Binary** (`adherence_type="binary"`):
- Pass/fail only (score is 0.0 or 1.0)
- Use for hard constraints: "must never X", "must always Y"
- Regulatory, security, safety requirements
- Programmatic checks (version strings, regex)

**Float** (`adherence_type="float"`):
- Continuous score 0.0–1.0
- Use for soft constraints: "should usually X", "prefer Y"
- Tone, style, quality metrics

### How do I set rule severity?

Severity weights (0.0–1.0) reflect importance:
- **1.0**: Critical (regulatory, security)
- **0.7–0.9**: Important for correctness
- **0.4–0.6**: Nice-to-have (style, tone)
- **0.0–0.3**: Optional suggestions

Severity affects the weighted adherence score. Binary rule failures always floor to 0 regardless of severity.

### How many rules should a policy have?

**3–10 rules** is typical for most policies.

- Too few (1–2): May miss important constraints
- Too many (20+): Consider sequential mode or splitting into sub-policies

No hard limit — we've tested policies with 50+ rules.

### Can rules reference each other?

Not yet. Rule dependencies are a planned feature:
```python
Rule(id="R2", depends_on=["R1"])  # Future
```

For now, use conditional logic in programmatic evaluators or split into separate policies.

## Testing

### How do I use PolicyEval in pytest?

PolicyEval auto-registers a pytest plugin when installed:

```python
from policyeval import assert_policy, Policy, Rule

def test_compliance():
    policy = Policy(name="Test", rules=[...])
    
    assert_policy(
        input="user query",
        output=bot_response,
        policy=policy,
        min_adherence=0.9,
        min_coverage=0.7,
    )
```

CLI overrides:
```bash
pytest --policyeval-model gpt-4o-mini --policyeval-system-prompt "..."
```

### Why do my tests fail in CI but pass locally?

Common causes:

1. **Different models**: CI uses `gpt-4o-mini`, local uses `gpt-4o`
   - Solution: Pin model in tests or use `--policyeval-model` consistently
2. **Missing `OPENAI_API_KEY`** in CI
   - Solution: Add to GitHub Secrets / GitLab Variables
3. **Flaky LLM responses**
   - Solution: Use programmatic evaluators for critical rules

### How do I mock LLM calls in tests?

Use a mock judge:

```python
from policyeval.judges.base import LLMJudge

class MockJudge(LLMJudge):
    async def complete(self, system_prompt: str, prompt: str) -> str:
        raise NotImplementedError  # unused by PolicyTest

    def complete_sync(self, system_prompt: str, prompt: str) -> str:
        raise NotImplementedError  # unused by PolicyTest

    async def evaluate(self, system_prompt: str, prompt: str) -> dict:
        return self.evaluate_sync(system_prompt, prompt)

    def evaluate_sync(self, system_prompt: str, prompt: str) -> dict:
        return {
            "adherence": {"score": 1.0, "rule_results": [...]},
            "coverage": {"score": 1.0, "uncovered_actions": []},
        }

test = PolicyTest(input="...", output="...", policy=policy, judge=MockJudge())
```

PolicyEval's own test suite uses this pattern — the full suite runs offline, no API keys required.

### What's a good threshold for compliance?

Depends on your domain:

**High-stakes** (legal, healthcare, finance):
- Adherence: ≥ 0.95
- Coverage: ≥ 0.90
- Compliance: ≥ 0.92

**Medium-stakes** (customer support, content moderation):
- Adherence: ≥ 0.85
- Coverage: ≥ 0.70
- Compliance: ≥ 0.80

**Low-stakes** (style guides, recommendations):
- Adherence: ≥ 0.70
- Coverage: ≥ 0.50

Better: **Use separate thresholds** instead of relying on compliance alone:
```python
assert report.adherence.score >= 0.90
assert report.coverage.score >= 0.70
```

## Generation

### Does `PolicyExecutor` guarantee compliance?

No. `PolicyExecutor` prompts the LLM with the policy rules, but the LLM may not follow them perfectly.

**Always evaluate after generation**:
```python
result = PolicyExecutor(policy=policy, input=query).run()
report = PolicyTest(input=query, output=result.output, policy=policy).run()
```

Compose a retry loop if needed:
```python
for attempt in range(3):
    result = executor.run()
    report = PolicyTest(..., output=result.output, ...).run()
    if report.compliance_score >= 0.9:
        break
```

### Can I guide generation with partial outputs?

Not directly. `PolicyExecutor` generates from scratch.

For constrained decoding, you'd need to:
1. Use a model that supports grammars (e.g., llama.cpp, Outlines)
2. Subclass `LLM` to wrap that model
3. Pass programmatic constraints

### Can I use PolicyExecutor for streaming?

Not yet. `PolicyExecutor` returns the full output.

Streaming is a planned feature.

## Integration

### Can I load policies from files?

Yes! YAML and JSON:

**YAML:**
```yaml
name: Financial Advice Safety
version: "1.0"
rules:
  - id: no_advice
    description: Must not provide personalized investment advice
    severity: 1.0
    adherence_type: binary
```

Load:
```python
from policyeval.policy.loader import load_policy

policy = load_policy("policy.yaml")
```

### Can I convert text to a policy?

Yes! Use `extract_rules()`:

```python
from policyeval import extract_rules, Policy
from policyeval.llm import OpenAILLM

policy = """
1. Upgrade docker to v25.0.4
2. Update go.sum
3. Replace ContainerJSON
"""

rules = extract_rules(policy, llm=OpenAILLM(model="gpt-4o"))
policy = Policy(name="Docker Upgrade", rules=rules)
```

### How do I integrate with CI/CD?

**GitHub Actions:**
```yaml
- name: Run policy tests
  env:
    OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
  run: uv run pytest tests/test_plan_compliance.py --policyeval-model gpt-4o-mini
```

**GitLab CI:**
```yaml
policy-tests:
  script:
    - uv run pytest tests/test_plan_compliance.py --policyeval-model gpt-4o-mini
```

See [CI/CD Integration](GUIDE.md#cicd-integration) for full examples.

### Can I use PolicyEval with LangChain?

Yes, but PolicyEval doesn't depend on LangChain. Use it:

**After LangChain generation:**
```python
from langchain import OpenAI
from policyeval import PolicyTest

llm = OpenAI()
output = llm(prompt)

report = PolicyTest(input=prompt, output=output, policy=policy).run()
```

**Or replace the LLM layer:**
```python
from policyeval.llm.base import LLM

class LangChainLLM(LLM):
    def __init__(self, langchain_llm):
        self.llm = langchain_llm
    
    def complete_sync(self, system_prompt: str, prompt: str) -> str:
        return self.llm(f"{system_prompt}\n\n{prompt}")
```

## Troubleshooting

### "No OPENAI_API_KEY found"

Set your API key:
```bash
export OPENAI_API_KEY=sk-...
```

Or pass it explicitly:
```python
from policyeval.llm import OpenAILLM

llm = OpenAILLM(api_key="sk-...")
```

### "Policy must have at least one rule"

You passed an empty rules list:
```python
policy = Policy(name="Test", rules=[])  # ❌
```

Fix:
```python
policy = Policy(name="Test", rules=[Rule(...)])  # ✓
```

### "Expected RuleResult, got None"

Your programmatic evaluator returned `None` instead of a `RuleResult`:
```python
def my_evaluator(input, output, rule):
    if condition:
        return RuleResult(...)  # ✓
    # Missing return here! ❌
```

Always return a `RuleResult`:
```python
def my_evaluator(input, output, rule):
    passed = check_condition(output)
    return RuleResult(
        rule_id=rule.id,
        score=1.0 if passed else 0.0,
        adherence_type=rule.adherence_type,
        severity=rule.severity,
        reasoning=f"Condition {'passed' if passed else 'failed'}",
        source="programmatic",
    )
```

### LLM returns malformed JSON

The judge failed to return valid JSON. This can happen with:
- Very complex policies (20+ rules)
- Unclear rule descriptions
- Models without JSON mode support

Solutions:
1. Use a model with JSON mode (e.g., `gpt-4o`)
2. Simplify rule descriptions
3. Use sequential mode: `eval_mode="sequential"`
4. Add retries (built into `OpenAIJudge`)

### Tests are slow

Optimizations:
1. Use `gpt-4o-mini` (faster than `gpt-4o`)
2. Run adherence-only: `test.run(metrics=["adherence"])`
3. Use programmatic evaluators (no LLM call)
4. Mock judges in unit tests
5. Run full evaluations only on main branch

## Contributing

### How can I contribute?

See [CONTRIBUTING.md](../CONTRIBUTING.md) for:
- Development setup
- Running tests
- Submitting PRs
- Adding examples

### I found a bug. What should I do?

Open an [issue](https://github.com/Backline-AI/PolicyEval/issues) with:
- Python version
- PolicyEval version (`pip show policyeval`)
- Minimal reproduction code
- Expected vs actual behavior

### I have a feature request.

Open a [discussion](https://github.com/Backline-AI/PolicyEval/discussions) or issue! We're actively developing and welcome feedback.

## More Questions?

- **Email**: haggai.shachar@backline.ai
- **GitHub Issues**: https://github.com/Backline-AI/PolicyEval/issues
- **GitHub Discussions**: https://github.com/Backline-AI/PolicyEval/discussions
