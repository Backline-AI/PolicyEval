"""Load :class:`~policyeval.policy.models.Policy` objects from YAML or JSON files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Union

import yaml

from policyeval.policy.models import Policy


def load_policy(source: Union[str, Path]) -> Policy:
    """Load a :class:`Policy` from a YAML or JSON file.

    Args:
        source: Path to a ``.yaml``, ``.yml``, or ``.json`` file.

    Returns:
        A validated :class:`Policy` instance.

    Raises:
        ValueError: If the file extension is not recognised or the content
            fails Pydantic validation.
        FileNotFoundError: If the file does not exist.

    Example::

        policy = load_policy("policies/financial_advice.yaml")
    """
    path = Path(source)
    if not path.exists():
        raise FileNotFoundError(f"Policy file not found: {path}")

    suffix = path.suffix.lower()
    if suffix in {".yaml", ".yml"}:
        with path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    elif suffix == ".json":
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    else:
        raise ValueError(
            f"Unsupported file format '{suffix}'. Use .yaml, .yml, or .json."
        )

    if not isinstance(data, dict):
        raise ValueError("Policy file must contain a mapping at the top level.")

    return Policy.model_validate(data)


def load_policy_from_dict(data: dict) -> Policy:
    """Construct a :class:`Policy` from a plain dictionary.

    Useful when the policy definition is already parsed (e.g. embedded in
    a larger config file).
    """
    return Policy.model_validate(data)


def load_policy_from_string(text: str, fmt: str = "yaml") -> Policy:
    """Parse a policy from a raw string.

    Args:
        text: The raw policy text.
        fmt: ``"yaml"`` (default) or ``"json"``.

    Returns:
        A validated :class:`Policy` instance.
    """
    fmt = fmt.lower()
    if fmt in {"yaml", "yml"}:
        data = yaml.safe_load(text)
    elif fmt == "json":
        data = json.loads(text)
    else:
        raise ValueError(f"Unsupported format '{fmt}'. Use 'yaml' or 'json'.")

    if not isinstance(data, dict):
        raise ValueError("Policy string must contain a mapping at the top level.")

    return Policy.model_validate(data)
