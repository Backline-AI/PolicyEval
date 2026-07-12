# Contributing to PolicyEval

Thanks for your interest in contributing! This guide covers how to set up a
development environment, run the tests, and submit changes.

## Development Setup

PolicyEval uses [uv](https://github.com/astral-sh/uv) for dependency management.

```bash
git clone https://github.com/Backline-AI/PolicyEval.git
cd PolicyEval

# Install the package with dev dependencies into a local virtual env
uv sync --dev
```

## Running the Tests

The full test suite runs **offline** — it uses mock judges and does not require
an API key or make network calls.

```bash
# Run everything
uv run pytest

# Verbose
uv run pytest -v

# A single file or test
uv run pytest tests/test_engine.py
uv run pytest -k "adherence"
```

Tests live in [`tests/`](tests/) and are configured in `pyproject.toml`
(`asyncio_mode = "auto"`, so `async def test_*` functions run without extra
decorators).

## Making a Change

1. **Branch** off `main`:
   ```bash
   git checkout -b fix/short-description
   ```
2. **Write code and tests.** New behavior needs a test; bug fixes should include
   a regression test.
3. **Keep the public API in sync.** If you add or rename anything exported from
   the package, update `policyeval/__init__.py` (`__all__`) and the relevant
   docs under [`docs/`](docs/).
4. **Update docs and the changelog.** Add a note under `[Unreleased]` in
   [`CHANGELOG.md`](CHANGELOG.md) for anything user-facing.
5. **Run the tests** and make sure they pass.
6. **Open a pull request** against `main` and fill out the template.

## Commit Messages

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add sequential evaluation mode
fix: correct coverage score when no actions are found
docs: clarify severity weighting
test: cover binary fail-fast behavior
```

## Adding an Example

Examples live in [`examples/`](examples/) and are a great first contribution:

1. Create `examples/your_example.py` with a docstring explaining what it shows
   and how to run it.
2. Keep it self-contained and runnable with `python examples/your_example.py`.
3. Add a row to the **Examples** table in the [README](README.md).

## Project Layout

```
policyeval/
├── policy/         # Policy and Rule models, loading, text extraction
├── engine/       # Evaluation and execution orchestration
├── metrics/      # Adherence, coverage, compliance scoring
├── llm/          # LLM abstraction (base + OpenAI-compatible)
├── judges/       # LLM-as-judge implementations
├── reporting/    # Report data models
├── testing/      # PolicyTest, PolicyExecutor, pytest plugin
└── cli/          # Command-line interface
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for how these fit together.

## Reporting Bugs and Requesting Features

Open an [issue](https://github.com/Backline-AI/PolicyEval/issues). For bugs,
please include your Python version, PolicyEval version, and a minimal
reproduction.

## License

By contributing, you agree that your contributions will be licensed under the
[MIT License](LICENSE).
