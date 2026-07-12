"""Tests for the rule extractor."""

import json

import pytest

from policyeval.policy.extractor import (
    _parse_json,
    extract_rules,
    extract_rules_async,
)
from policyeval.policy.models import AdherenceType
from tests.conftest import MockJudge


EXTRACTOR_RESPONSE = {
    "rules": [
        {
            "id": "upgrade_docker",
            "description": "Upgrade docker to v25.0.0",
            "adherence_type": "binary",
            "severity": 1.0,
        },
        {
            "id": "replace_api",
            "description": "Replace ContainerJSON with InspectResponse",
            "adherence_type": "binary",
            "severity": 0.8,
        },
    ]
}


class TestExtractRules:
    def test_basic_extraction(self):
        llm = MockJudge(EXTRACTOR_RESPONSE)
        rules = extract_rules("some text", llm=llm)
        assert len(rules) == 2
        assert rules[0].id == "upgrade_docker"
        assert rules[1].severity == 0.8

    def test_adherence_type_parsed(self):
        llm = MockJudge(EXTRACTOR_RESPONSE)
        rules = extract_rules("text", llm=llm)
        assert rules[0].adherence_type == AdherenceType.binary

    def test_default_severity_applied(self):
        response = {"rules": [{"id": "R1", "description": "Do something"}]}
        llm = MockJudge(response)
        rules = extract_rules("text", llm=llm, default_severity=0.5)
        assert rules[0].severity == 0.5

    def test_empty_rules_raises(self):
        llm = MockJudge({"rules": []})
        with pytest.raises(ValueError, match="empty"):
            extract_rules("text", llm=llm)

    def test_missing_rules_key_raises(self):
        llm = MockJudge({"something": "else"})
        with pytest.raises(ValueError, match="'rules' array"):
            extract_rules("text", llm=llm)

    def test_custom_system_prompt_used(self):
        llm = MockJudge(EXTRACTOR_RESPONSE)
        extract_rules("text", llm=llm, system_prompt="Custom prompt")
        assert llm.calls[0][0] == "Custom prompt"

    def test_fallback_id_when_missing(self):
        response = {"rules": [{"description": "Do something without id"}]}
        llm = MockJudge(response)
        rules = extract_rules("text", llm=llm)
        assert rules[0].id == "rule_1"

    def test_invalid_adherence_type_falls_back_to_default(self):
        response = {
            "rules": [{"id": "R1", "description": "d", "adherence_type": "nonsense"}]
        }
        llm = MockJudge(response)
        rules = extract_rules("text", llm=llm, default_adherence_type="float")
        assert rules[0].adherence_type == AdherenceType.float

    def test_non_dict_items_skipped(self):
        response = {"rules": ["not a dict", {"id": "R1", "description": "d"}]}
        llm = MockJudge(response)
        rules = extract_rules("text", llm=llm)
        assert len(rules) == 1
        assert rules[0].id == "R1"


class TestExtractRulesAsync:
    async def test_basic_async_extraction(self):
        llm = MockJudge(EXTRACTOR_RESPONSE)
        rules = await extract_rules_async("some text", llm=llm)
        assert len(rules) == 2
        assert rules[0].id == "upgrade_docker"

    async def test_async_empty_rules_raises(self):
        llm = MockJudge({"rules": []})
        with pytest.raises(ValueError):
            await extract_rules_async("text", llm=llm)

    async def test_async_missing_rules_key_raises(self):
        llm = MockJudge({"nope": 1})
        with pytest.raises(ValueError, match="'rules' array"):
            await extract_rules_async("text", llm=llm)

    async def test_async_custom_system_prompt(self):
        llm = MockJudge(EXTRACTOR_RESPONSE)
        await extract_rules_async("text", llm=llm, system_prompt="Custom")
        assert llm.calls[0][0] == "Custom"


class TestParseJson:
    def test_plain_json(self):
        assert _parse_json('{"a": 1}') == {"a": 1}

    def test_triple_backtick_fence_with_lang(self):
        text = '```json\n{"a": 1}\n```'
        assert _parse_json(text) == {"a": 1}

    def test_triple_backtick_fence_no_closing(self):
        text = '```\n{"a": 2}'
        assert _parse_json(text) == {"a": 2}

    def test_single_backtick(self):
        assert _parse_json('`{"a": 3}`') == {"a": 3}

    def test_roundtrip(self):
        payload = {"rules": [{"id": "x"}]}
        assert _parse_json(json.dumps(payload)) == payload
