# PolicyEval Architecture

This document explains the internal architecture of PolicyEval.

## Design Goals

1. **Separation of concerns**: Generation and evaluation are distinct operations
2. **Composability**: Users control the generate → evaluate → retry flow
3. **Extensibility**: Plug in any LLM/judge via base classes
4. **Type safety**: Pydantic models throughout with full type hints
5. **Independence**: Adherence and coverage are computed independently
6. **Offline testing**: Mock judges allow testing without API calls

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         User Interface                          │
├─────────────┬─────────────┬──────────────┬────────────────────┤
│  Python API │  pytest     │  CLI         │  Policy Files      │
│             │  plugin     │              │  (YAML/JSON)       │
└──────┬──────┴──────┬──────┴──────┬───────┴────────┬───────────┘
       │             │             │                │
       ▼             ▼             ▼                ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Engine Layer                              │
├──────────────────────────┬──────────────────────────────────────┤
│  PolicyExecutor          │  PolicyTest (Evaluator)              │
│  (Generation)            │  (Evaluation)                        │
│                          │                                      │
│  • Takes policy + input  │  • Takes policy + input + output     │
│  • Calls LLM with rules  │  • Calls LLMJudge for scoring        │
│    as constraints        │  • Routes to adherence/coverage      │
│  • Returns generated     │    calculators                       │
│    text                  │  • Returns PolicyReport              │
└──────────┬───────────────┴────────────────┬─────────────────────┘
           │                                │
           ▼                                ▼
┌──────────────────────┐      ┌────────────────────────────────────┐
│   LLM Abstraction    │      │      Metrics Layer                 │
├──────────────────────┤      ├────────────────────────────────────┤
│  LLM (base)          │      │  • Adherence calculator            │
│  └─ OpenAILLM        │      │  • Coverage calculator             │
│                      │      │  • Compliance calculator           │
│  LLMJudge (base)     │      │                                    │
│  └─ OpenAIJudge      │      │  Handles:                          │
└──────────────────────┘      │  • Weighted scoring                │
                              │  • Binary rule fail-fast           │
                              │  • Harmonic/arithmetic mean        │
                              │  • Programmatic evaluator routing  │
                              └────────────────────────────────────┘
```

## Module Breakdown

### `policy/` — Policy Models and Utilities

**`policy/models.py`**
- `Policy`: Container for rules + metadata
- `Rule`: Single requirement with severity, type, optional evaluator
- Pydantic models with validation

**`policy/loader.py`**
- `load_policy(path)`: YAML/JSON → `Policy`
- Auto-detects format from extension

**`policy/extractor.py`**
- `extract_rules(text, llm)`: Unstructured text → `list[Rule]`
- Uses LLM with structured output schema

### `engine/` — Core Execution Logic

**`engine/executor.py`**
- `PolicyExecutor`: Policy-guided generation
- Constructs prompt from policy rules
- Calls `LLM.complete()` for text generation
- Returns `ExecutionResult`

**`engine/evaluator.py`**
- `PolicyTest`: Orchestrates evaluation
- Routes to adherence/coverage calculators
- Handles metric selection (`["adherence"]`, `["coverage"]`, both)
- Returns `PolicyReport`

### `metrics/` — Scoring Algorithms

**`metrics/adherence.py`**
- `AdherenceCalculator`
- Batch mode: Single LLM call for all rules
- Sequential mode: One LLM call per rule
- Programmatic evaluators bypass LLM
- Implements weighted severity scoring
- Binary rule fail-fast logic

**`metrics/coverage.py`**
- `CoverageCalculator`
- Prompts LLM to find uncovered actions
- Severity-weighted coverage score
- Returns `CoverageReport` with uncovered actions list

**`metrics/compliance.py`**
- `calculate_compliance(adherence, coverage, weights)`
- Weighted harmonic mean (if both > 0)
- Arithmetic mean fallback (if either = 0)

### `llm/` — LLM Abstraction Layer

**`llm/base.py`**
- `LLM`: Abstract base for any LLM
- Methods: `complete()`, `complete_sync()`

**`llm/openai.py`**
- `OpenAILLM`: OpenAI-compatible implementation
- Supports OpenAI, Azure, LiteLLM, any OpenAI-compatible endpoint
- Constructor params: `model`, `api_key`, `base_url`, `temperature`, `max_tokens`

### `judges/` — LLM Judge Implementations

**`judges/base.py`**
- `LLMJudge`: Extends `LLM` with structured evaluation
- Adds: `evaluate()`, `evaluate_sync()` → `dict`
- Used for compliance scoring (not generation)

**`judges/openai_judge.py`**
- `OpenAIJudge`: OpenAI-compatible judge
- JSON mode enabled
- Temperature = 0 (deterministic)
- Retry logic with exponential backoff

### `reporting/` — Report Data Models

**`reporting/models.py`**
- `PolicyReport`: Top-level report
  - `adherence: AdherenceReport | None`
  - `coverage: CoverageReport | None`
  - `compliance_score: float | None`
- `AdherenceReport`: Rule-level results
  - `score: float`
  - `rule_results: list[RuleResult]`
- `CoverageReport`: Uncovered actions
  - `score: float`
  - `uncovered_actions: list[UncoveredAction]`
- `RuleResult`: Single rule evaluation
- `UncoveredAction`: Unexpected action in output

### `testing/` — Pytest Integration

**`testing/plugin.py`**
- Pytest plugin (auto-registered via entry point)
- CLI flags: `--policyeval-model`, `--policyeval-system-prompt`
- Session summary at end of test run

**`testing/test_case.py`**
- `assert_policy()`: Pytest assertion function
- Runs `PolicyTest`, checks thresholds
- Detailed failure messages

### `cli/` — Command-Line Interface

**`cli/main.py`**
- Typer-based CLI
- Commands:
  - `run`: Evaluate outputs against policy
  - `execute`: Generate compliant outputs
  - `validate`: Check policy file syntax
- Rich output formatting

## Data Flow

### Evaluation Flow

```
User Call: PolicyTest(input, output, policy).run()
    │
    ▼
PolicyTest.run(metrics=["adherence", "coverage"])
    │
    ├──> AdherenceCalculator
    │        │
    │        ├──> Programmatic evaluators (if any)
    │        │        └──> RuleResult (no LLM call)
    │        │
    │        └──> LLMJudge.evaluate() for LLM rules
    │                 │
    │                 └──> Batch: Single call, all rules
    │                 └──> Sequential: One call per rule
    │                 └──> Returns list[RuleResult]
    │        │
    │        └──> Weighted scoring + binary fail-fast
    │        └──> AdherenceReport
    │
    ├──> CoverageCalculator
    │        │
    │        └──> LLMJudge.evaluate() for uncovered actions
    │        └──> Severity-weighted scoring
    │        └──> CoverageReport
    │
    └──> calculate_compliance()
         └──> PolicyReport(adherence, coverage, compliance_score)
```

### Generation Flow

```
User Call: PolicyExecutor(policy, input).run()
    │
    ▼
PolicyExecutor.run()
    │
    ├──> Build prompt from policy rules
    │        │
    │        └──> "You must follow these rules:\n1. ..."
    │
    ├──> LLM.complete(system_prompt, prompt)
    │        │
    │        └──> OpenAI API call (or LiteLLM, Azure, etc.)
    │
    └──> ExecutionResult(output, policy_name, timestamp, metadata)
```

## Key Design Decisions

### 1. Generation and Evaluation Are Separate

**Why**: Users need control over the retry loop.

**Not this**:
```python
# Hidden evaluate-on-generate flag
executor.run(auto_evaluate=True, min_score=0.9, retry=3)
```

**This**:
```python
# User composes the loop
for attempt in range(3):
    result = executor.run()
    report = PolicyTest(input=..., output=result.output, policy=policy).run()
    if report.compliance_score >= 0.9:
        break
```

### 2. Adherence and Coverage Are Independent

**Why**: They measure different failure modes.

- High adherence, low coverage = follows rules but does unexpected things
- Low adherence, high coverage = violates rules but doesn't surprise

Both matter. The compliance score is a summary; the sub-reports are the substance.

### 3. Severity Is User-Defined

**Why**: The user knows which rules are critical; the LLM doesn't.

- Rule severity: user-defined (static)
- Uncovered action severity: LLM-determined (dynamic)

### 4. Programmatic Evaluators Are First-Class

**Why**: Deterministic checks (version strings, regex) shouldn't need LLM calls.

Rules with an `evaluator` function skip the LLM entirely:
```python
Rule(
    id="version_check",
    description="...",
    evaluator=my_function,  # No LLM call
)
```

Mix programmatic and LLM-evaluated rules in the same policy.

### 5. Batch Mode Is Default

**Why**: Faster and cheaper for most use cases.

Batch mode: Single LLM call evaluates all rules at once.
- Trade-off: May miss nuance in complex policies.

Sequential mode: One call per rule.
- Trade-off: Slower and more expensive.

Users can choose via `eval_mode="sequential"`.

### 6. Binary Rules Fail Fast

**Why**: A single critical violation should fail the entire adherence.

If **any** binary rule has `score=0.0`, adherence is floored to `0.0`.

This implements "any hard constraint violation = fail" semantics.

### 7. Independent Metrics Save LLM Calls

**Why**: CI checks often only need adherence; coverage is expensive.

```python
# Fast: adherence only (no coverage call)
report = test.run(metrics=["adherence"])

# Slow: both (default)
report = test.run()
```

Use adherence-only for CI; full evaluation for nightly audits.

## Extensibility Points

### Custom LLM for Generation

Subclass `LLM`:
```python
from policyeval.llm.base import LLM

class MyLLM(LLM):
    async def complete(self, system_prompt: str, prompt: str) -> str:
        # Your implementation
        pass

    def complete_sync(self, system_prompt: str, prompt: str) -> str:
        # Your implementation
        pass
```

Use it:
```python
executor = PolicyExecutor(policy=policy, input="...", llm=MyLLM())
```

### Custom Judge for Evaluation

Subclass `LLMJudge`:
```python
from policyeval.judges.base import LLMJudge

class MyJudge(LLMJudge):
    async def evaluate(self, system_prompt: str, prompt: str) -> dict:
        # Must return dict matching expected schema
        pass

    def evaluate_sync(self, system_prompt: str, prompt: str) -> dict:
        # Sync version
        pass
```

Use it:
```python
test = PolicyTest(input="...", output="...", policy=policy, judge=MyJudge())
```

### Custom Metric

Add a new metric calculator in `metrics/` and wire it into `PolicyTest.run()`.

Steps:
1. Create `metrics/my_metric.py` with a calculator class
2. Add field to `PolicyReport` in `reporting/models.py`
3. Call calculator in `engine/evaluator.py`
4. Update CLI to support new metric

## Testing Strategy

### Mock Judges

Tests use mock judges to avoid LLM API calls. `LLMJudge` requires all four methods
(`complete`, `complete_sync`, `evaluate`, `evaluate_sync`) to be implemented:

```python
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
```

The full test suite runs offline with no API keys required.

### Test Structure

```
tests/
├── conftest.py                  # Fixtures, mock judges
├── test_policy_models.py         # Policy, Rule validation
├── test_engine.py               # PolicyTest, PolicyExecutor
├── test_executor.py             # PolicyExecutor generation
├── test_metrics.py              # Adherence, coverage, compliance
├── test_independent_metrics.py  # Single-metric (adherence-only / coverage-only) runs
├── test_judge.py                # LLMJudge, OpenAIJudge
├── test_llm.py                  # LLM, OpenAILLM
├── test_reporting.py            # Report models and serialization
├── test_policy_loader.py         # YAML/JSON loading
├── test_extractor.py            # Text-to-rules extraction
├── test_pytest_plugin.py        # Pytest integration
└── test_cli.py                  # CLI commands
```

## Performance Considerations

### LLM Call Minimization

- Programmatic evaluators: 0 calls per rule
- Batch mode: 1 call per evaluation (all rules)
- Sequential mode: N calls (one per rule)
- Coverage: 1 call per evaluation

**Example**: Policy with 5 rules, adherence + coverage
- Batch: 2 LLM calls total
- Sequential: 6 LLM calls (5 adherence + 1 coverage)

### Async Support

All LLM calls have async variants:
```python
# Sync
report = test.run()
result = executor.run()

# Async
report = await test.arun()
result = await executor.arun()
```

Useful for concurrent evaluations:
```python
reports = await asyncio.gather(*[
    test.arun() for test in test_cases
])
```

## Future Architecture Considerations

### Caching

Future: Cache LLM evaluation results by (policy, input, output) hash.
- Requires: Deterministic prompt construction
- Invalidation: On policy or LLM version change

### Streaming

Future: Stream generation from `PolicyExecutor`.
- Challenge: Policy guidance may require full output before validation

### Batch Evaluation API

Future: Evaluate multiple outputs in one call.
```python
batch_report = PolicyTest.batch_run(
    policy=policy,
    cases=[(input1, output1), (input2, output2), ...]
)
```

### Multi-Policy Evaluation

Future: Evaluate against multiple policies at once.
```python
multi_report = PolicyTest(
    input=...,
    output=...,
    policies=[policy1, policy2, policy3],
).run()
```

### Rule Dependencies

Future: Express dependencies between rules.
```python
Rule(
    id="R2",
    description="...",
    depends_on=["R1"],  # Only evaluate if R1 passes
)
```

## Debugging Tips

### Enable Logging

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

This logs:
- LLM prompts and responses
- Evaluation mode (batch/sequential)
- Programmatic evaluator invocations

### Inspect Prompts

Subclass `OpenAIJudge` to log prompts:
```python
class DebugJudge(OpenAIJudge):
    def evaluate_sync(self, system_prompt: str, prompt: str) -> dict:
        print(f"SYSTEM: {system_prompt}")
        print(f"PROMPT: {prompt}")
        return super().evaluate_sync(system_prompt, prompt)
```

### Check Report JSON

```python
report = test.run()
print(report.model_dump_json(indent=2))
```

Inspect:
- Per-rule scores and reasoning
- Uncovered actions with severity
- Overall score breakdown
