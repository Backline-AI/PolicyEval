# API Reference

Complete API documentation for PolicyEval.

## Core Classes

### Policy

Represents a set of rules that an LLM output should follow.

```python
from policyeval import Policy, Rule

policy = Policy(
    name="My Policy",
    rules=[...],
    description="Optional description",
    version="1.0"
)
```

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `name` | `str` | Yes | Policy name/identifier |
| `rules` | `list[Rule]` | Yes | List of rules (at least one required) |
| `description` | `str` | No | Human-readable policy description |
| `version` | `str` | No | Version string for tracking policy changes |

**Methods:**

- `get_rule(rule_id: str) -> Rule | None` — Look up a rule by id
- `model_dump() -> dict`, `model_dump_json() -> str` — Pydantic serialization
- `model_validate(data: dict) -> Policy` — Pydantic deserialization (classmethod)

For file-based YAML/JSON loading, use [`load_policy`](#load_policy) instead of constructing `Policy` by hand.

---

### Rule

A single requirement or constraint in a policy.

```python
from policyeval import Rule

rule = Rule(
    id="unique_id",
    description="Clear statement of the requirement",
    severity=1.0,
    adherence_type="binary",
    scope="optional context",
    evaluator=optional_function
)
```

**Parameters:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `id` | `str` | Yes | — | Unique identifier within the policy |
| `description` | `str` | Yes | — | Human-readable requirement statement |
| `severity` | `float` | No | `1.0` | Weight for scoring (0.0–1.0) |
| `adherence_type` | `"binary"` \| `"float"` | No | `"binary"` | Scoring mode |
| `scope` | `str` | No | `None` | Optional context or domain hint |
| `evaluator` | `Callable` | No | `None` | Programmatic evaluation function |

**Adherence Types:**

- **`binary`**: Pass/fail only (score is 0.0 or 1.0). Use for hard constraints.
- **`float`**: Continuous score 0.0–1.0. Use for soft constraints or degrees of compliance.

**Evaluator Function Signature:**

```python
def evaluator(input: str, output: str, rule: Rule) -> RuleResult:
    # Your deterministic logic here
    return RuleResult(
        rule_id=rule.id,
        score=1.0 if condition else 0.0,
        adherence_type=rule.adherence_type,
        severity=rule.severity,
        reasoning="Explanation of the result",
        source="programmatic",
    )
```

---

### PolicyTest

Evaluates an LLM output against a policy.

```python
from policyeval import PolicyTest, Policy
from policyeval.judges.openai_judge import OpenAIJudge

test = PolicyTest(
    input="The original prompt",
    output="The LLM's response",
    policy=policy,
    judge=OpenAIJudge(),
    system_prompt="You are a compliance officer.",
    eval_mode="batch",
    adherence_weight=1.0,
    coverage_weight=1.0,
)

# Synchronous
report = test.run(metrics=["adherence", "coverage"])

# Async
report = await test.arun(metrics=["adherence", "coverage"])
```

**Parameters:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `input` | `str` | Yes | — | Original prompt or context |
| `output` | `str` | Yes | — | LLM response to evaluate |
| `policy` | `Policy` | Yes | — | Policy to evaluate against |
| `judge` | `LLMJudge` | No | `OpenAIJudge()` | Judge instance |
| `system_prompt` | `str` | No | `None` | Judge persona/domain context |
| `eval_mode` | `"batch"` \| `"sequential"` | No | `"batch"` | Evaluation strategy |
| `adherence_weight` | `float` | No | `1.0` | Weight for compliance score |
| `coverage_weight` | `float` | No | `1.0` | Weight for compliance score |

**Evaluation Modes:**

- **`batch`** (default): Single LLM call evaluates all rules at once. Faster, cheaper, but may be less precise.
- **`sequential`**: One LLM call per rule. Slower, more expensive, but more focused reasoning per rule.

**Methods:**

- `run(metrics: list[str] | None = None) -> PolicyReport` — Synchronous evaluation
- `arun(metrics: list[str] | None = None) -> PolicyReport` — Async evaluation

**Metrics Parameter:**

- `None` (default): Run both adherence and coverage
- `["adherence"]`: Run adherence only
- `["coverage"]`: Run coverage only
- `["adherence", "coverage"]`: Run both (same as `None`)

---

### PolicyExecutor

Generates a policy-compliant response for a given input.

```python
from policyeval import PolicyExecutor, Policy
from policyeval.llm import OpenAILLM

executor = PolicyExecutor(
    policy=policy,
    input="User query or prompt",
    llm=OpenAILLM(model="gpt-4"),
    system_prompt="You are a helpful assistant.",
)

# Synchronous
result = executor.run()
print(result.output)

# Async
result = await executor.arun()
print(result.output)
```

**Parameters:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `policy` | `Policy` | Yes | — | Policy whose rules guide generation |
| `input` | `str` | Yes | — | User query or context to respond to |
| `llm` | `LLM` | No | `OpenAILLM()` | LLM for generation |
| `system_prompt` | `str` | No | `None` | Optional persona or domain context |

**Methods:**

- `run() -> ExecutionResult` — Synchronous generation
- `arun() -> ExecutionResult` — Async generation

---

### ExecutionResult

Result of a policy-guided generation.

**Fields:**

| Name | Type | Description |
|------|------|-------------|
| `output` | `str` | Generated text |
| `policy_name` | `str` | Name of the policy used |
| `generated_at` | `datetime` | UTC timestamp |
| `metadata` | `dict` | Policy version and other trace info |

---

### PolicyReport

Complete evaluation result containing adherence, coverage, and compliance scores.

**Fields:**

| Name | Type | Description |
|------|------|-------------|
| `adherence` | `AdherenceReport \| None` | Per-rule adherence results |
| `coverage` | `CoverageReport \| None` | Uncovered action detection |
| `compliance_score` | `float \| None` | Combined score (0.0–1.0) |
| `reasoning` | `str` | Overall summary combining both dimensions |
| `evaluated_at` | `datetime` | UTC timestamp |
| `metadata` | `dict` | Arbitrary trace info (model, policy name, …) |

**Methods:**

- `model_dump(mode="json") -> dict`, `model_dump_json() -> str` — Pydantic serialization
- `passed(min_adherence=None, min_coverage=None, min_compliance=None) -> bool` — Check thresholds

---

### AdherenceReport

Adherence evaluation results.

**Fields:**

| Name | Type | Description |
|------|------|-------------|
| `score` | `float` | Weighted adherence score (0.0–1.0) |
| `rule_results` | `list[RuleResult]` | Per-rule results |
| `reasoning` | `str` | Overall adherence summary |

---

### CoverageReport

Coverage evaluation results.

**Fields:**

| Name | Type | Description |
|------|------|-------------|
| `score` | `float` | Coverage score (0.0–1.0) |
| `uncovered_actions` | `list[UncoveredAction]` | Unexpected actions detected |
| `reasoning` | `str` | Overall coverage summary |

---

### RuleResult

Evaluation result for a single rule.

**Fields:**

| Name | Type | Description |
|------|------|-------------|
| `rule_id` | `str` | ID of the evaluated rule |
| `score` | `float` | 0.0–1.0 for float rules, 0.0 or 1.0 for binary |
| `adherence_type` | `"binary"` \| `"float"` | Scoring mode |
| `severity` | `float` | Rule severity (0.0–1.0) |
| `reasoning` | `str` | Explanation of the score |
| `source` | `"llm"` \| `"programmatic"` | How the rule was evaluated |
| `passed` | `bool` | For binary rules: whether it passed |

---

### UncoveredAction

An action in the output not covered by any policy rule.

**Fields:**

| Name | Type | Description |
|------|------|-------------|
| `description` | `str` | What the uncovered action is |
| `severity` | `float` | LLM-determined severity (0.0–1.0) |
| `reasoning` | `str` | Why no rule covers it |

---

## LLM Abstraction

### LLM (Base Class)

Abstract base for any LLM used in generation.

```python
from policyeval.llm.base import LLM

class CustomLLM(LLM):
    async def complete(self, system_prompt: str, prompt: str) -> str:
        # Your implementation
        pass

    def complete_sync(self, system_prompt: str, prompt: str) -> str:
        # Your implementation
        pass
```

**Methods to Implement:**

- `async complete(system_prompt: str, prompt: str) -> str` — Async completion
- `complete_sync(system_prompt: str, prompt: str) -> str` — Sync completion

---

### OpenAILLM

OpenAI-compatible LLM implementation. Supports OpenAI API, Azure, LiteLLM, and any OpenAI-compatible endpoint.

```python
from policyeval.llm import OpenAILLM

# Standard OpenAI
llm = OpenAILLM(model="gpt-4")

# LiteLLM proxy
llm = OpenAILLM(
    model="anthropic/claude-3-opus",
    base_url="http://localhost:4000"
)

# Azure OpenAI
llm = OpenAILLM(
    model="gpt-4",
    base_url="https://your-resource.openai.azure.com",
    api_key="your-azure-key"
)
```

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `model` | `str` | `"gpt-4o"` | Model identifier |
| `api_key` | `str` | `None` | API key (defaults to `OPENAI_API_KEY` env var) |
| `base_url` | `str` | `None` | Custom endpoint URL |
| `temperature` | `float` | `0.7` | Sampling temperature |
| `max_tokens` | `int` | `2000` | Max completion tokens |

---

### LLMJudge (Base Class)

Abstract base for any LLM used in evaluation. Extends `LLM` with structured evaluation.

```python
from policyeval.judges.base import LLMJudge

class CustomJudge(LLMJudge):
    async def complete(self, system_prompt: str, prompt: str) -> str:
        # Text completion
        pass

    def complete_sync(self, system_prompt: str, prompt: str) -> str:
        # Sync text completion
        pass

    async def evaluate(self, system_prompt: str, prompt: str) -> dict:
        # Structured JSON evaluation
        pass

    def evaluate_sync(self, system_prompt: str, prompt: str) -> dict:
        # Sync structured evaluation
        pass
```

**Methods to Implement:**

All methods from `LLM`, plus:

- `async evaluate(system_prompt: str, prompt: str) -> dict` — Async structured evaluation
- `evaluate_sync(system_prompt: str, prompt: str) -> dict` — Sync structured evaluation

---

### OpenAIJudge

OpenAI-compatible judge implementation.

```python
from policyeval.judges.openai_judge import OpenAIJudge

# Standard OpenAI
judge = OpenAIJudge(model="gpt-4o")

# LiteLLM proxy
judge = OpenAIJudge(
    model="anthropic/claude-3-opus",
    base_url="http://localhost:4000"
)
```

**Parameters:** Same as `OpenAILLM`.

---

## Utilities

### extract_rules

Convert unstructured text into `Rule` objects using an LLM.

```python
from policyeval import extract_rules, Policy
from policyeval.llm import OpenAILLM

rules = extract_rules(
    text="1. Upgrade docker to v25.0.0\n2. Replace ContainerJSON",
    llm=OpenAILLM(model="gpt-4o"),
    default_adherence_type="binary",
    default_severity=1.0,
)

policy = Policy(name="My Policy", rules=rules)
```

**Parameters:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `text` | `str` | Yes | — | Unstructured requirements text |
| `llm` | `LLM` | No | `OpenAILLM()` | LLM for extraction |
| `default_adherence_type` | `"binary"` \| `"float"` | No | `"binary"` | Default for extracted rules |
| `default_severity` | `float` | No | `1.0` | Default severity |

**Returns:** `list[Rule]`

An async variant, `extract_rules_async`, is also exported for use inside existing event loops.

---

### load_policy

Load a policy from a YAML or JSON file.

```python
from policyeval.policy.loader import load_policy

policy = load_policy("path/to/policy.yaml")
# or
policy = load_policy("path/to/policy.json")
```

**Related loaders:**

- `load_policy_from_dict(data: dict) -> Policy` — Build a policy from an already-parsed dict
- `load_policy_from_string(text: str, fmt: str = "yaml") -> Policy` — Parse a policy from a raw YAML or JSON string

```python
from policyeval import load_policy_from_dict, load_policy_from_string

policy = load_policy_from_dict({"name": "My Policy", "rules": [...]})
policy = load_policy_from_string(yaml_text, fmt="yaml")
```

---

## Pytest Integration

### assert_policy

Assert that an LLM output meets policy requirements. Auto-registered via pytest plugin.

```python
from policyeval import assert_policy, Policy, Rule

def test_compliance():
    policy = Policy(
        name="Test Policy",
        rules=[Rule(id="R1", description="Must not X", severity=1.0)]
    )

    assert_policy(
        input="user query",
        output="llm response",
        policy=policy,
        min_adherence=0.8,
        min_coverage=0.7,
    )
```

**Parameters:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `input` | `str` | Yes | — | Original prompt |
| `output` | `str` | Yes | — | LLM response |
| `policy` | `Policy` | Yes | — | Policy to evaluate against |
| `metrics` | `list[str]` | No | `None` (both) | Which metrics to run |
| `min_score` | `float` | No | `None` | Minimum score for single-metric tests |
| `min_adherence` | `float` | No | `None` | Minimum adherence score |
| `min_coverage` | `float` | No | `None` | Minimum coverage score |
| `min_compliance` | `float` | No | `None` | Minimum compliance score |
| `judge` | `LLMJudge` | No | `OpenAIJudge()` | Judge instance |
| `system_prompt` | `str` | No | `None` | Judge persona |

**CLI Overrides:**

```bash
pytest --policyeval-model gpt-4o-mini \
       --policyeval-system-prompt "You are a compliance expert."
```

---

## CLI Commands

### policyeval extract

Turn a plain-English policy document into a structured policy YAML. An LLM
decomposes the text into individually evaluable rules.

```bash
policyeval extract <text_file> [OPTIONS]
```

**Options:**

| Flag | Description | Default |
|------|-------------|---------|
| `-o, --output` | Write generated policy YAML to file | stdout |
| `-n, --name` | Policy name | source file stem |
| `--adherence-type` | Default `adherence_type` for extracted rules (`binary`/`float`) | `binary` |
| `--severity` | Default severity (0–1) for extracted rules | `1.0` |
| `--system-prompt` | Extractor persona | none |
| `--model` | LLM model name | `gpt-4o` |
| `--base-url` | Custom LLM endpoint | OpenAI default |

**Example:**

```bash
policyeval extract policy.md -o policy.yaml --name "Financial Advice Safety"
```

The output loads directly with `policyeval run`/`validate` or `load_policy()`. Review and
tune severities by hand before relying on it.

---

### policyeval run

Evaluate agent interactions against a policy. The interactions file (YAML or
JSON) holds one `{"input": "...", "output": "..."}` object or an array of them
(batch mode). An optional `"context"` field adds background for changes not
covered by rules.

```bash
policyeval run <policy_file> <interactions_file> [OPTIONS]
```

**Options:**

| Flag | Description | Default |
|------|-------------|---------|
| `--eval-mode` | `batch` or `sequential` | `batch` |
| `--metrics` | `adherence`, `coverage`, or both | both |
| `-f, --format` | Render stdout as `text`, `markdown`, or `json` | `text` |
| `--threshold` | Pass/fail cutoff for a score (0–1) | `0.5` |
| `--adherence-weight` | Weight for adherence in the compliance score | `1.0` |
| `--coverage-weight` | Weight for coverage in the compliance score | `1.0` |
| `-o, --output` | Save report to file (Markdown when `--format markdown`, else JSON) | stdout |
| `--system-prompt` | Judge persona | none |
| `--model` | LLM model name | `gpt-4o` |
| `--base-url` | Custom LLM endpoint | OpenAI default |

**Example:**

```bash
policyeval run policy.yaml interactions.json --eval-mode sequential -o report.json
```

---

### policyeval execute

Generate policy-compliant outputs.

```bash
policyeval execute <policy_file> [OPTIONS]
```

**Options:**

| Flag | Description | Default |
|------|-------------|---------|
| `--input` | Single input to generate for | required (or file) |
| `--inputs` | JSON file with batch inputs | — |
| `--temperature` | Sampling temperature for generation | `0.7` |
| `-o, --output` | Save results to file | stdout |
| `--system-prompt` | Generation persona | none |
| `--model` | LLM model name | `gpt-4o` |
| `--base-url` | Custom LLM endpoint | OpenAI default |

**Example:**

```bash
policyeval execute policy.yaml --input "Should I buy Tesla stock?" -o result.json
```

---

### policyeval validate

Validate a policy file's syntax.

```bash
policyeval validate <policy_file>
```

---

## Scoring Formulas

### Adherence Score

```
adherence = Σ(rule.score × rule.severity) / Σ(rule.severity)
```

If **any** binary rule fails (score = 0), adherence is floored to 0.

### Coverage Score

```
coverage = 1.0 - (Σ uncovered_action.severity) / n_actions
```

Where `n_actions` is the number of uncovered actions.

### Compliance Score

```python
if adherence > 0 and coverage > 0:
    # Weighted harmonic mean
    compliance = (w_a + w_c) / (w_a / adherence + w_c / coverage)
else:
    # Arithmetic mean fallback
    compliance = (w_a * adherence + w_c * coverage) / (w_a + w_c)
```

Where `w_a` = `adherence_weight` and `w_c` = `coverage_weight` (default 1.0 each).

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key | required |
| `OPENAI_BASE_URL` | Custom OpenAI endpoint | `https://api.openai.com/v1` |
| `POLICYEVAL_MODEL` | Default model for CLI/tests | `gpt-4o` |
