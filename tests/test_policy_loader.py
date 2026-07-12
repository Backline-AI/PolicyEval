"""Tests for the YAML/JSON policy loader."""

import json

import pytest
import yaml

from policyeval.policy.loader import (
    load_policy,
    load_policy_from_dict,
    load_policy_from_string,
)
from policyeval.policy.models import AdherenceType


SAMPLE_DICT = {
    "name": "Test Policy",
    "version": "1.0",
    "rules": [
        {
            "id": "R1",
            "description": "Rule one",
            "severity": 1.0,
            "adherence_type": "binary",
        },
        {
            "id": "R2",
            "description": "Rule two",
            "severity": 0.5,
            "adherence_type": "float",
        },
    ],
}


class TestLoadFromFile:
    def test_load_yaml(self, tmp_path):
        f = tmp_path / "policy.yaml"
        f.write_text(yaml.dump(SAMPLE_DICT))
        policy = load_policy(f)
        assert policy.name == "Test Policy"
        assert len(policy.rules) == 2

    def test_load_yml_extension(self, tmp_path):
        f = tmp_path / "policy.yml"
        f.write_text(yaml.dump(SAMPLE_DICT))
        policy = load_policy(f)
        assert policy.name == "Test Policy"

    def test_load_json(self, tmp_path):
        f = tmp_path / "policy.json"
        f.write_text(json.dumps(SAMPLE_DICT))
        policy = load_policy(f)
        assert policy.name == "Test Policy"

    def test_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_policy(tmp_path / "missing.yaml")

    def test_unsupported_extension(self, tmp_path):
        f = tmp_path / "policy.toml"
        f.write_text("name = 'test'")
        with pytest.raises(ValueError, match="Unsupported"):
            load_policy(f)

    def test_adherence_type_preserved(self, tmp_path):
        f = tmp_path / "policy.yaml"
        f.write_text(yaml.dump(SAMPLE_DICT))
        policy = load_policy(f)
        assert policy.rules[0].adherence_type == AdherenceType.binary
        assert policy.rules[1].adherence_type == AdherenceType.float


class TestLoadFromDict:
    def test_basic(self):
        policy = load_policy_from_dict(SAMPLE_DICT)
        assert len(policy.rules) == 2

    def test_invalid_dict(self):
        with pytest.raises(Exception):
            load_policy_from_dict({"name": "No rules"})


class TestLoadFromString:
    def test_yaml_string(self):
        s = yaml.dump(SAMPLE_DICT)
        policy = load_policy_from_string(s, fmt="yaml")
        assert policy.name == "Test Policy"

    def test_json_string(self):
        s = json.dumps(SAMPLE_DICT)
        policy = load_policy_from_string(s, fmt="json")
        assert policy.name == "Test Policy"

    def test_unsupported_format(self):
        with pytest.raises(ValueError):
            load_policy_from_string("...", fmt="toml")
