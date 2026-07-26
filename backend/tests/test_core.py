import json
import sys
import time
from types import ModuleType

import pandas as pd
import pytest

from app.common.errors import AgentError, ProviderError
from app.common.runtime_settings.runtime_settings_store import (
    hash_password,
    verify_password,
)
from app.dal.providers.flapi.mapper import FlunksMapper
from app.dal.providers.flapi.provider import FlapiProvider
from app.dal.providers.flapi.runner_config import (
    build_flapi_config, resolve_timeout,
)
from app.repository import Repository
from app.bl.workflow_engine import _SECTION_SCHEMA, SummaryService


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


def test_normalized_records_are_json_serializable(monkeypatch):
    """flunks returns a DataFrame, so pandas types reach ``save_evidence``.

    ``Repository.save_evidence`` hands records straight to ``Jsonb``. A
    ``Timestamp`` or ``NaT`` in a FLAPI time cube is not JSON serializable, so
    an unconverted cell aborts the whole evidence write - the run loses every
    row of that step, not just the one column.
    """
    _install_fake_flunks(monkeypatch)

    records = FlunksMapper().normalize(pd.DataFrame([
        {"id": "001", "eventTime": pd.Timestamp("2026-07-24T10:00:00Z")},
        {"id": "002", "eventTime": pd.NaT},
    ]))

    assert json.dumps(records)
    assert records[0]["eventTime"] == "2026-07-24T10:00:00+00:00"
    assert records[1]["eventTime"] is None


def test_normalize_keeps_numeric_identifier_columns_as_strings(monkeypatch):
    """A locked decision: numeric-looking identifiers stay strings.

    pandas types a column of digits as int64, so ``00123`` arrives as the int
    ``123``. Stringifying only at fan-out is too late - the evidence row and
    the Hebrew prompt would already have lost the leading zeros.
    """
    _install_fake_flunks(monkeypatch)

    records = FlunksMapper().normalize(
        pd.DataFrame({"id": pd.Series(["00123", "456"], dtype="string")})
    )

    assert [record["id"] for record in records] == ["00123", "456"]


def test_normalize_rejects_duplicate_columns_instead_of_dropping_them(
    monkeypatch
):
    """flunks joins cubes, so duplicate column names are reachable.

    ``DataFrame.to_dict('records')`` silently keeps only the last of each
    duplicate name and warns. Losing a column of evidence without an error
    would make the summary quietly incomplete.
    """
    _install_fake_flunks(monkeypatch)
    frame = pd.DataFrame([["x", "y"]], columns=["id", "id"])

    with pytest.raises(ProviderError, match="עמודות כפולות"):
        FlunksMapper().normalize(frame)


def test_normalize_accepts_an_empty_dataframe(monkeypatch):
    """A package that legitimately matched nothing must not look like a failure."""
    _install_fake_flunks(monkeypatch)

    assert FlunksMapper().normalize(pd.DataFrame(columns=["id"])) == []


def test_password_is_hashed_and_verified():
    encoded = hash_password("private value", salt=b"0123456789abcdef")

    assert "private value" not in encoded
    assert verify_password("private value", encoded)
    assert not verify_password("wrong", encoded)


def test_flapi_provider_retries_once_and_adds_query_provenance(monkeypatch):
    _install_fake_flunks(monkeypatch)

    class Settings:
        flapi_username = "fde"
        flapi_token = "token"

    class Store:
        @staticmethod
        def get():
            return Settings()

    attempts = []

    class Runner:
        def __init__(self, attempt):
            self.attempt = attempt

        def run(self):
            if self.attempt == 1:
                raise RuntimeError("temporary")
            return pd.DataFrame([{"name": "בית"}])

    def factory(_settings, _config):
        attempts.append(len(attempts) + 1)
        return Runner(attempts[-1])

    provider = FlapiProvider(Store(), runner_factory=factory)
    records = provider.run({
        "package_key": "home",
        "package_id": "PKG-007",
        "input_cube_name": "root",
        "input_cube_parameter": "identifier",
        "output_cube_name": "facts",
        "query_name": "home-summary",
    }, ["001"])

    assert attempts == [1, 2]
    assert records == [{"name": "בית", "_package_query": "home-summary"}]


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


def test_step_reading_earlier_output_must_declare_it_as_a_dependency():
    with pytest.raises(ValueError, match="תלויות"):
        Repository._validate_steps([
            {"key": "first", "input_source": "workflow.id", "depends_on": []},
            {
                "key": "second",
                "input_source": "steps.first",
                "input_field": "home_id",
                "depends_on": [],
            },
        ])

    Repository._validate_steps([
        {"key": "first", "input_source": "workflow.id", "depends_on": []},
        {
            "key": "second",
            "input_source": "steps.first",
            "input_field": "home_id",
            "depends_on": ["first"],
        },
    ])


def test_package_run_is_bounded_by_the_configured_timeout(monkeypatch):
    _install_fake_flunks(monkeypatch)

    class Settings:
        flapi_username = "fde"
        flapi_token = "token"
        flapi_verify_tls = True
        package_timeout_seconds = 120

    class Store:
        @staticmethod
        def get():
            return Settings()

    class HangingRunner:
        @staticmethod
        def run():
            time.sleep(30)
            raise AssertionError("the timeout should have fired first")

    provider = FlapiProvider(
        Store(), runner_factory=lambda _s, _c: HangingRunner()
    )
    started = time.monotonic()
    with pytest.raises(ProviderError, match="חרגה מזמן הריצה"):
        provider.run({
            "package_key": "slow",
            "package_id": "PKG-1",
            "input_cube_name": "root",
            "input_cube_parameter": "identifier",
            "output_cube_name": "facts",
            "timeout_seconds": 1,
        }, ["001"])

    # Two attempts of a 1s bound must not approach the 120s global default.
    assert time.monotonic() - started < 10


def test_package_timeout_falls_back_to_the_global_setting(monkeypatch):
    _install_fake_flunks(monkeypatch)

    class Settings:
        flapi_username = "fde"
        flapi_token = "token"
        flapi_verify_tls = True
        package_timeout_seconds = 45

    class Store:
        @staticmethod
        def get():
            return Settings()

    settings = Settings()

    assert resolve_timeout({"timeout_seconds": 7}, settings) == 7
    assert resolve_timeout({"timeout_seconds": None}, settings) == 45
    assert resolve_timeout({}, settings) == 45


def test_verify_tls_reaches_flapi_config_only_when_the_field_exists():
    class Settings:
        flapi_username = "fde"
        flapi_token = "token"
        flapi_verify_tls = False

    class ModernConfig:
        model_fields = {"username": None, "token": None, "verify_tls": None}

        def __init__(self, **values):
            self.__dict__.update(values)

    class LegacyConfig:
        model_fields = {"username": None, "token": None}

        def __init__(self, **values):
            self.__dict__.update(values)

    modern = build_flapi_config(ModernConfig, Settings())
    assert modern.verify_tls is False

    # An older wheel without the field must still build, not raise.
    legacy = build_flapi_config(LegacyConfig, Settings())
    assert not hasattr(legacy, "verify_tls")
    assert legacy.username == "fde"


def test_failed_workflow_keeps_successful_sections_visible():
    class FakeRepository:
        @staticmethod
        def published_content(_key, fallback):
            return fallback

    class FakeLlm:
        @staticmethod
        def complete_json(_system, _user, _schema):
            raise AgentError("llm unavailable")

    class FakeStore:
        @staticmethod
        def get():
            class Values:
                max_parallel_workflows = 2
            return Values()

    service = SummaryService(FakeRepository(), None, FakeLlm(), FakeStore())

    def execute(run, root_id, workflow, save_evidence=True):
        if workflow["workflow_key"] == "broken":
            raise RuntimeError("package exploded")
        return {
            "workflow_id": workflow["id"],
            "workflow_key": workflow["workflow_key"],
            "name": workflow["name"],
            "status": "completed",
            "summary": "סיכום",
            "facts": ["עובדה"],
            "warnings": [],
            "suggested_questions": [],
            "evidence_ids": ["ev-1"],
        }

    service._execute_workflow = execute
    result = service._execute(
        {"id": "run-1", "question": "מה קורה?"},
        "ROOT-1",
        "מה קורה?",
        [
            {"id": "w1", "workflow_key": "healthy", "name": "תקין"},
            {"id": "w2", "workflow_key": "broken", "name": "שבור"},
        ],
        lambda *_args: None,
    )

    by_key = {s["workflow_key"]: s for s in result["sections"]}
    assert by_key["healthy"]["status"] == "completed"
    assert by_key["broken"]["status"] == "failed"
    assert result["partial"] is True
    # The successful section's facts survive the sibling failure.
    assert "עובדה" in result["key_findings"]


def test_progress_is_reported_for_every_completed_workflow():
    class FakeRepository:
        @staticmethod
        def published_content(_key, fallback):
            return fallback

    class FakeLlm:
        @staticmethod
        def complete_json(_system, _user, _schema):
            raise AgentError("llm unavailable")

    class FakeStore:
        @staticmethod
        def get():
            class Values:
                max_parallel_workflows = 2
            return Values()

    service = SummaryService(FakeRepository(), None, FakeLlm(), FakeStore())
    service._execute_workflow = lambda run, root_id, workflow, **_kw: {
        "workflow_id": workflow["id"],
        "workflow_key": workflow["workflow_key"],
        "name": workflow["name"],
        "status": "completed",
        "summary": "", "facts": [], "warnings": [],
        "suggested_questions": [], "evidence_ids": [],
    }

    seen = []
    service._execute(
        {"id": "run-1", "question": "q"},
        "ROOT-1",
        "q",
        [
            {"id": "w1", "workflow_key": "a", "name": "A"},
            {"id": "w2", "workflow_key": "b", "name": "B"},
        ],
        lambda completed, total, _sections: seen.append((completed, total)),
    )

    assert seen[0] == (0, 2)
    assert seen[-1] == (2, 2)


def test_workflow_output_schema_extends_the_shared_section_contract():
    merged = SummaryService._merge_output_schema({
        "properties": {
            "owner_name": {"type": "string"},
            "summary": {"type": "number"},
        },
        "required": ["owner_name"],
    })

    # The FDE field is added...
    assert merged["properties"]["owner_name"] == {"type": "string"}
    assert "owner_name" in merged["required"]
    # ...but it cannot redefine a contract field the frontend renders.
    assert merged["properties"]["summary"] == {"type": "string"}
    assert set(merged["required"]) >= set(_SECTION_SCHEMA["required"])

    # A malformed or empty schema degrades to the shared contract.
    assert SummaryService._merge_output_schema({}) is _SECTION_SCHEMA
    assert SummaryService._merge_output_schema(None) is _SECTION_SCHEMA
    assert SummaryService._merge_output_schema(
        {"properties": "nonsense"}
    ) is _SECTION_SCHEMA


def test_custom_output_schema_fields_are_captured_separately():
    class FakeLlm:
        received_schema = None

        def complete_json(self, _system, _user, schema):
            self.received_schema = schema
            return {
                "summary": "סיכום",
                "facts": ["עובדה"],
                "warnings": [],
                "suggested_questions": [],
                "owner_name": "דנה",
            }

    llm = FakeLlm()
    service = SummaryService(None, None, llm, None)
    generated = service._section_summary(
        {
            "name": "בעלות",
            "system_prompt": "",
            "output_schema": {"properties": {"owner_name": {"type": "string"}}},
        },
        [],
        [],
    )

    assert "owner_name" in llm.received_schema["properties"]
    assert generated["summary"] == "סיכום"
    # The custom field is kept out of the rendered contract keys.
    assert generated["fields"] == {"owner_name": "דנה"}


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


def test_fde_prompt_builds_a_draft_only_from_existing_tools():
    tools = [{
        "id": "tool-v1",
        "name": "בעלות",
        "description": "מחזיר פרטי בעלות",
        "agent_instructions": "סכם בעלים וקשרים.",
        "input_mode": "single",
        "input_cube_parameter": "identifier",
        "example_output": [{"owner_id": "001", "owner_name": "דנה"}],
    }]

    class FakeRepository:
        @staticmethod
        def list_packages():
            return tools

        @staticmethod
        def published_content(_key, fallback):
            return fallback

    class FakeLlm:
        received = None

        def complete_json(self, _system, user, _schema):
            self.received = json.loads(user)
            return {
                "name": "בדיקת בעלות",
                "description": "מעמיק בבעלות",
                "role": "detail",
                "rationale": "הטול הקיים מכסה את הבקשה.",
                "system_prompt": "סכם עובדות בעלות בלבד.",
                "steps": [{
                    "key": "ownership",
                    "name": "שליפת בעלות",
                    "package_version_id": "tool-v1",
                    "depends_on": [],
                    "input_source": "workflow.id",
                    "input_field": "",
                    "summary_prompt": "הדגש בעלים.",
                }],
                "missing_tools": [],
            }

    llm = FakeLlm()
    service = SummaryService(FakeRepository(), None, llm, None)
    plan = service.plan_workflow("בנה תהליך לבדיקת בעלות")

    assert plan["can_build"] is True
    assert plan["steps"][0]["package_version_id"] == "tool-v1"
    assert llm.received["available_tools"][0]["output_fields"] == [
        "owner_id", "owner_name",
    ]


def test_workflow_plan_rejects_an_invented_tool():
    plan = SummaryService._validated_plan({
        "name": "לא תקין",
        "description": "",
        "role": "detail",
        "rationale": "",
        "system_prompt": "",
        "steps": [{
            "key": "invented",
            "name": "טול מומצא",
            "package_version_id": "missing",
            "depends_on": [],
            "input_source": "workflow.id",
            "input_field": "",
            "summary_prompt": "",
        }],
        "missing_tools": [],
    }, [{"id": "real"}])

    assert plan["can_build"] is False
    assert plan["steps"] == []
    assert plan["missing_tools"][0]["name"] == "טול שלא קיים בקטלוג"


def test_follow_up_can_select_an_approved_tool_without_a_workflow():
    tool = {
        "id": "tool-v1",
        "package_key": "ownership",
        "name": "בעלות",
        "description": "מעמיק בבעלות",
        "agent_instructions": "סכם בעלים בלבד.",
    }

    class FakeRepository:
        @staticmethod
        def published_workflows(_roles):
            return []

        @staticmethod
        def agent_tools():
            return [tool]

        @staticmethod
        def run_evidence(_run_id):
            return []

    service = SummaryService(FakeRepository(), None, None, None)
    service._select_detail = lambda *_args, **_kwargs: {
        "action": "tool",
        "tool_version_id": "tool-v1",
    }
    captured = {}

    def execute(_run, _root_id, _question, workflows, _progress):
        captured["workflow"] = workflows[0]
        return {"summary": "ok"}

    service._execute = execute
    result = service.follow_up(
        {"id": "run-2", "question": "מי הבעלים?"},
        {"root_id": "001", "runs": []},
        lambda *_args: None,
    )

    assert result == {"summary": "ok"}
    assert captured["workflow"]["id"] == "tool:tool-v1"
    assert captured["workflow"]["steps"][0]["package_version_id"] == "tool-v1"
    assert captured["workflow"]["system_prompt"] == "סכם בעלים בלבד."
