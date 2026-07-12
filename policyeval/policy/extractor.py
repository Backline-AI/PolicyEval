"""LLM-powered text-to-rules extractor.

Converts unstructured or semi-structured text (e.g. a remediation policy,
an insurance policy document, a legal contract) into a list of structured
:class:`~policyeval.policy.models.Rule` objects.
"""

from __future__ import annotations

import json
from typing import Optional

from policyeval.llm.base import LLM
from policyeval.policy.models import AdherenceType, Rule

_EXTRACTOR_SYSTEM_PROMPT = (
    "You are an expert at decomposing policy documents, policies, and requirements "
    "into discrete, individually evaluable rules. Each rule should be a single, "
    "clear, testable statement. Return only valid JSON."
)

_EXTRACTOR_PROMPT_TEMPLATE = """\
Analyse the following text and extract a list of discrete, evaluable rules.

TEXT:
{text}

Instructions:
- Extract one rule per distinct requirement, action, or constraint.
- For each rule return:
  - "id": a short snake_case identifier (e.g. "upgrade_docker", "no_investment_advice")
  - "description": the requirement as a clear, evaluable statement
  - "adherence_type": "{default_adherence_type}"
  - "severity": {default_severity}
- Do NOT merge unrelated requirements into one rule.
- Do NOT add rules that are not explicitly present in the text.

Return a JSON object with a single key "rules" containing an array of rule objects.
Example output:
{{
  "rules": [
    {{"id": "upgrade_docker", "description": "Upgrade github.com/docker/docker to v25.0.0", "adherence_type": "binary", "severity": 1.0}},
    {{"id": "replace_container_json", "description": "Replace deprecated ContainerJSON with InspectResponse", "adherence_type": "binary", "severity": 0.8}}
  ]
}}
"""


def extract_rules(
    text: str,
    llm: LLM,
    system_prompt: Optional[str] = None,
    default_adherence_type: str = "binary",
    default_severity: float = 1.0,
) -> list[Rule]:
    """Extract structured :class:`Rule` objects from unstructured text.

    Uses an LLM to decompose the text into individually evaluable rules.
    This is a convenience utility – you can always construct :class:`Rule`
    objects manually.

    Args:
        text: The source text to parse (remediation policy, policy document, etc.).
        llm: An :class:`~policyeval.llm.base.LLM` instance used to perform
            the extraction.  Any :class:`~policyeval.judges.base.LLMJudge`
            works here too since it extends ``LLM``.
        system_prompt: Optional custom system prompt to override the default
            extractor persona.
        default_adherence_type: Default ``adherence_type`` for extracted rules
            (``"binary"`` or ``"float"``).  Defaults to ``"binary"``.
        default_severity: Default severity weight (0–1) for extracted rules.
            Defaults to ``1.0``.

    Returns:
        A list of :class:`Rule` objects parsed from the LLM's response.

    Raises:
        ValueError: If the LLM response cannot be parsed or contains no rules.

    Example::

        from policyeval import extract_rules, Policy
        from policyeval.llm import OpenAILLM

        rules = extract_rules(
            text="1. Upgrade docker to v25.0.0\\n2. Replace ContainerJSON with InspectResponse",
            llm=OpenAILLM(model="gpt-4o"),
            default_adherence_type="binary",
            default_severity=1.0,
        )
        policy = Policy(name="SCA Remediation", rules=rules)
    """
    sys_prompt = system_prompt or _EXTRACTOR_SYSTEM_PROMPT
    user_prompt = _EXTRACTOR_PROMPT_TEMPLATE.format(
        text=text,
        default_adherence_type=default_adherence_type,
        default_severity=default_severity,
    )

    raw_text = llm.complete_sync(sys_prompt, user_prompt)
    raw = _parse_json(raw_text)

    rules_data = raw.get("rules")
    if rules_data is None or not isinstance(rules_data, list):
        raise ValueError(
            f"Extractor LLM response did not contain a 'rules' array. Got: {json.dumps(raw)}"
        )
    if len(rules_data) == 0:
        raise ValueError("Extractor returned an empty rules list.")

    rules: list[Rule] = []
    for i, item in enumerate(rules_data):
        if not isinstance(item, dict):
            continue
        adherence_raw = item.get("adherence_type", default_adherence_type)
        try:
            adherence = AdherenceType(adherence_raw)
        except ValueError:
            adherence = AdherenceType(default_adherence_type)

        rule = Rule(
            id=str(item.get("id", f"rule_{i + 1}")),
            description=str(item.get("description", "")),
            severity=float(item.get("severity", default_severity)),
            adherence_type=adherence,
            scope=item.get("scope"),
        )
        rules.append(rule)

    if not rules:
        raise ValueError("Extractor returned an empty rules list.")

    return rules


async def extract_rules_async(
    text: str,
    llm: LLM,
    system_prompt: Optional[str] = None,
    default_adherence_type: str = "binary",
    default_severity: float = 1.0,
) -> list[Rule]:
    """Async variant of :func:`extract_rules`."""
    sys_prompt = system_prompt or _EXTRACTOR_SYSTEM_PROMPT
    user_prompt = _EXTRACTOR_PROMPT_TEMPLATE.format(
        text=text,
        default_adherence_type=default_adherence_type,
        default_severity=default_severity,
    )

    raw_text = await llm.complete(sys_prompt, user_prompt)
    raw = _parse_json(raw_text)

    rules_data = raw.get("rules")
    if not rules_data or not isinstance(rules_data, list):
        raise ValueError(
            f"Extractor LLM response did not contain a 'rules' array. Got: {json.dumps(raw)}"
        )

    rules: list[Rule] = []
    for i, item in enumerate(rules_data):
        if not isinstance(item, dict):
            continue
        adherence_raw = item.get("adherence_type", default_adherence_type)
        try:
            adherence = AdherenceType(adherence_raw)
        except ValueError:
            adherence = AdherenceType(default_adherence_type)

        rule = Rule(
            id=str(item.get("id", f"rule_{i + 1}")),
            description=str(item.get("description", "")),
            severity=float(item.get("severity", default_severity)),
            adherence_type=adherence,
            scope=item.get("scope"),
        )
        rules.append(rule)

    if not rules:
        raise ValueError("Extractor returned an empty rules list.")

    return rules


def _parse_json(text: str) -> dict:
    """Parse JSON from a raw LLM text response.

    Strips markdown code fences (triple or single backticks) if present
    before parsing.
    """
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        inner = (
            "\n".join(lines[1:-1])
            if lines[-1].strip() == "```"
            else "\n".join(lines[1:])
        )
        stripped = inner.strip()
    elif stripped.startswith("`") and stripped.endswith("`"):
        stripped = stripped[1:-1].strip()
    return json.loads(stripped)
