import json
import sys
from types import ModuleType

import pandas as pd
import pytest

from app.common.runtime_settings.runtime_settings_store import (
    hash_password,
    verify_password,
)
from app.dal.providers.flapi.mapper import FlunksMapper
from app.repository import Repository
from app.workflows import SummaryService


def _install_fake_flunks(monkeypatch):
    config = ModuleType("flunks.config")
    flow_models = ModuleType("flunks.flow_models")
    root = ModuleType("flunks")

    class Model:
        def __init__(self, **values):
            self.__dict__.update(values)

    config.FlunksPackageConfig = Model
    flow_models.PackageInputCube = Model
    flow_models.PackageOutputCube = Model
    monkeypatch.setitem(sys.modules, "flunks", root)
    monkeypatch.setitem(sys.modules, "flunks.config", config)
    monkeypatch.setitem(sys.modules, "flunks.flow_models", flow_models)


def test_flunks_mapper_preserves_string_identifiers_and_generic_rows(monkeypatch):
    _install_fake_flunks(monkeypatch)
    mapper = FlunksMapper()
    package = {
        "package_id": "007",
        "input_cube_name": "root",
        "input_cube_parameter": "identifier",
        "output_cube_name": "facts",
    }

    mapped = mapper.package_config(package, ["001", "HOME-A/7"])

    assert mapped.package_id == "007"
    assert mapped.main_input_cube.values == ["001", "HOME-A/7"]
    assert mapper.normalize(pd.DataFrame([
        {"name": "בית", "score": 4},
        {"name": "סביבה", "score": None},
    ])) == [
        {"name": "בית", "score": 4.0},
        {"name": "סביבה", "score": None},
    ]


def test_password_is_hashed_and_verified():
    encoded = hash_password("private value", salt=b"0123456789abcdef")

    assert "private value" not in encoded
    assert verify_password("private value", encoded)
    assert not verify_password("wrong", encoded)


def test_workflow_identifier_mapping_supports_fanout_and_deduplication():
    step = {
        "input_source": "steps.near-home",
        "input_field": "home_id",
    }
    context = {
        "workflow": {"id": "ROOT-1"},
        "steps": {
            "near-home": [
                {"home_id": "001"},
                {"home_id": ["A-7", "001"]},
                {"home_id": None},
            ]
        },
    }

    assert SummaryService._identifiers(step, context) == ["001", "A-7"]


def test_invalid_workflow_cannot_reference_a_future_step():
    with pytest.raises(ValueError, match="שלב"):
        Repository._validate_steps([
            {
                "key": "first",
                "input_source": "steps.later",
                "input_field": "id",
                "depends_on": ["later"],
            },
            {
                "key": "later",
                "input_source": "workflow.id",
                "depends_on": [],
            },
        ])


def test_follow_up_router_can_choose_detail_workflow_despite_cached_evidence():
    class FakeRepository:
        @staticmethod
        def published_content(_key, fallback):
            return fallback

    class FakeLlm:
        received = None

        def complete_json(self, _system, user, _schema):
            self.received = json.loads(user)
            return {
                "action": "workflow",
                "workflow_key": "home-details",
                "clarification": None,
            }

    llm = FakeLlm()
    service = SummaryService(FakeRepository(), None, llm, None)
    selected = service._select_detail(
        "תן לי עוד פרטים על הבית",
        [{
            "workflow_key": "home-details",
            "name": "פרטי הבית",
            "description": "מידע מפורט על בית",
        }],
        [{"step_key": "baseline", "records": [{"name": "בית"}]}],
    )

    assert selected["workflow_key"] == "home-details"
    assert llm.received["existing_evidence"][0]["row_count"] == 1
