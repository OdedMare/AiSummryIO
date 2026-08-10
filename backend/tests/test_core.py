import json
import logging
import sys
import time
from types import ModuleType

import pandas as pd
import pytest
from pydantic import ValidationError

from app.common.errors import AgentError, ProviderError
from app.api.models import GeoBoundaries
from app.common.config.settings import Settings
from app.common.runtime_settings.normalizers import (
    extract_url_schema,
    normalize_database_schema,
    normalize_database_url,
    normalize_llm_base_url,
)
from app.common.runtime_settings.runtime_settings_store import (
    RuntimeSettingsStore,
)
from app.dal.providers.flapi.mapper import FlunksMapper
from app.dal.providers.flapi.provider import FlapiProvider
from app.dal.providers.flapi.runner_config import (
    build_flapi_config, resolve_timeout,
)
from app.dal.repository import Repository
from app.dal.repository.conversations import conversation_title
from app.dal.repository.validation import step_levels
from app.api.validation_errors import format_validation_error
from app.bl.workflow_engine import _SECTION_SCHEMA, SummaryService
from app.bl.workflow_engine_pkg import history
from app.bl.workflow_engine_pkg.execution import chunk_facts
from app.api.models import (
    ModelsProbeRequest, SkillPreview, SkillPreviewSection, SummaryCreate,
    WorkflowStep,
)


def test_flunks_mapper_preserves_string_identifiers_and_generic_rows():
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
    records = FlunksMapper().normalize(pd.DataFrame([
        {"id": "001", "eventTime": pd.Timestamp("2026-07-24T10:00:00Z")},
        {"id": "002", "eventTime": pd.NaT},
    ]))

    assert json.dumps(records)
    assert records[0]["eventTime"] == "2026-07-24T10:00:00+00:00"
    assert records[1]["eventTime"] is None


def test_normalize_does_not_coerce_identifier_strings_to_numbers(monkeypatch):
    """A locked decision: numeric-looking identifiers stay strings.

    pandas keeps a column of digit strings as ``object``, so ``00123`` survives
    on its own. What must never be added is a "looks numeric, cast it" step -
    this pins that, and pins that a genuine int64 cell stays an int rather than
    being stringified into a fake identifier.
    """
    records = FlunksMapper().normalize(pd.DataFrame([
        {"id": "00123", "count": 7},
        {"id": "456", "count": 8},
    ]))

    assert [record["id"] for record in records] == ["00123", "456"]
    assert [record["count"] for record in records] == [7, 8]


def test_normalize_rejects_duplicate_columns_instead_of_dropping_them(
    monkeypatch
):
    """flunks joins cubes, so duplicate column names are reachable.

    ``DataFrame.to_dict('records')`` silently keeps only the last of each
    duplicate name and warns. Losing a column of evidence without an error
    would make the summary quietly incomplete.
    """
    frame = pd.DataFrame([["x", "y"]], columns=["id", "id"])

    with pytest.raises(ProviderError, match="עמודות כפולות"):
        FlunksMapper().normalize(frame)


def test_normalize_accepts_an_empty_dataframe(monkeypatch):
    """A package that legitimately matched nothing must not look like a failure."""
    assert FlunksMapper().normalize(pd.DataFrame(columns=["id"])) == []


def test_flapi_provider_retries_once_and_adds_query_provenance(monkeypatch):
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


def test_flapi_outbound_diagnostic_is_comparable_without_leaking_secrets(
    caplog
):
    class Settings:
        flapi_username = "diagnostic-user"
        flapi_token = "top-secret-token"
        flapi_verify_tls = True

    package_config = FlunksMapper().package_config({
        "package_id": "PKG-007",
        "input_cube_name": "root",
        "input_cube_parameter": "identifier",
        "output_cube_name": "facts",
    }, ["001"])

    with caplog.at_level(logging.WARNING):
        runner = FlapiProvider._flunks_runner(Settings(), package_config)

    assert runner.flapi_config.username == "diagnostic-user"
    assert runner.flapi_config.token == "top-secret-token"
    assert "username='diagnostic-user'" in caplog.text
    assert "token=str:length=16:sha256=baed6367ed9d" in caplog.text
    assert "values=['001']" in caplog.text
    assert "package_id='PKG-007'" in caplog.text
    assert "top-secret-token" not in caplog.text


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


def test_a_saved_input_value_is_valid_and_reaches_the_package_unchanged():
    step = {
        "key": "fixed-input", "input_source": "workflow.value",
        "input_value": "00123-A", "depends_on": [],
    }

    Repository._validate_steps([step])
    assert SummaryService._identifiers(step, {
        "workflow": {"id": "ignored"}, "steps": {},
    }) == ["00123-A"]

    with pytest.raises(ValueError, match="ערך קלט"):
        Repository._validate_steps([dict(step, input_value="")])


def test_map_boundaries_reach_the_package_as_multipolygon_wkt():
    """The drawn area travels to flunks as one opaque WKT string."""
    step = {"input_source": "workflow.boundaries"}
    context = {
        "workflow": {
            "id": "ROOT-1",
            "boundaries": {
                "type": "MultiPolygon",
                "coordinates": [[[
                    [34.75, 32.05], [34.80, 32.05],
                    [34.80, 32.10], [34.75, 32.05],
                ]]],
            },
        },
        "steps": {},
    }

    assert SummaryService._identifiers(step, context) == [
        "MULTIPOLYGON (((34.75 32.05, 34.8 32.05, 34.8 32.1, 34.75 32.05)))"
    ]


def test_a_step_scoped_to_the_map_fails_clearly_without_a_drawn_area():
    step = {"input_source": "workflow.boundaries"}
    context = {"workflow": {"id": "ROOT-1", "boundaries": None}, "steps": {}}

    with pytest.raises(ValueError, match="אזור"):
        SummaryService._identifiers(step, context)


_SQUARE = {
    "type": "MultiPolygon",
    "coordinates": [[[
        [34.75, 32.05], [34.80, 32.05], [34.80, 32.10], [34.75, 32.05],
    ]]],
}


def test_boundaries_must_be_a_closed_multipolygon():
    ring = [[34.75, 32.05], [34.80, 32.05], [34.80, 32.10]]
    with pytest.raises(ValidationError):
        GeoBoundaries(type="MultiPolygon", coordinates=[[ring]])


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


def test_workflow_step_keys_accept_the_separators_generated_by_the_ui():
    for key in ("step-1", "step_2"):
        assert WorkflowStep(
            key=key, name="step", package_version_id="package"
        ).key == key


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


def test_a_step_scoped_to_the_drawn_area_is_a_valid_input_source():
    """workflow.boundaries used to fall through to the steps.<key> branch,
    so every workflow reading the map was rejected when it was saved."""
    Repository._validate_steps([
        {"key": "area", "input_source": "workflow.boundaries", "depends_on": []},
    ])


def test_steps_without_dependencies_share_one_parallel_level():
    steps = [
        {"key": "owners", "input_source": "workflow.id", "depends_on": []},
        {"key": "risks", "input_source": "workflow.id", "depends_on": []},
        {"key": "area", "input_source": "workflow.boundaries", "depends_on": []},
    ]
    Repository._validate_steps(steps)
    levels = step_levels(steps)
    assert [[step["key"] for step in level] for level in levels] == [
        ["owners", "risks", "area"]
    ]


def test_a_dependent_step_waits_for_the_level_that_feeds_it():
    levels = step_levels([
        {"key": "owners", "input_source": "workflow.id", "depends_on": []},
        {"key": "risks", "input_source": "workflow.id", "depends_on": []},
        {
            "key": "detail",
            "input_source": "steps.owners",
            "input_field": "owner_id",
            "depends_on": ["owners"],
        },
    ])
    assert [[step["key"] for step in level] for level in levels] == [
        ["owners", "risks"], ["detail"]
    ]


def test_a_fully_chained_workflow_still_runs_one_step_at_a_time():
    levels = step_levels([
        {"key": "first", "input_source": "workflow.id", "depends_on": []},
        {
            "key": "second", "input_source": "steps.first",
            "input_field": "id", "depends_on": ["first"],
        },
    ])
    assert [[step["key"] for step in level] for level in levels] == [
        ["first"], ["second"]
    ]


def test_circular_step_dependencies_are_reported_not_hung():
    with pytest.raises(ValueError, match="מעגלית"):
        step_levels([
            {"key": "a", "input_source": "steps.b", "depends_on": ["b"]},
            {"key": "b", "input_source": "steps.a", "depends_on": ["a"]},
        ])


def test_rejected_request_returns_one_readable_sentence_not_error_objects():
    class Rejected:
        @staticmethod
        def errors():
            return [{
                "loc": ("body", "steps", 0, "package_version_id"),
                "msg": "Field required",
                "type": "missing",
            }]

    detail = format_validation_error(Rejected())
    assert isinstance(detail, str)
    assert "טול" in detail
    assert "object" not in detail


def test_validation_detail_keeps_our_hebrew_message_without_pydantic_prefix():
    class Rejected:
        @staticmethod
        def errors():
            return [{
                "loc": ("body", "steps", 1, "key"),
                "msg": "Value error, מפתח שלב חייב להכיל אותיות, מספרים, _ או -",
                "type": "value_error",
            }]

    detail = format_validation_error(Rejected())
    assert detail.startswith("שלבים → פריט 2 → מפתח שלב:")
    assert "Value error" not in detail


def test_package_run_is_bounded_by_the_configured_timeout(monkeypatch):
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

    def execute(run, root_id, workflow, save_evidence=True, boundaries=None):
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


_OWNERSHIP_SECTION = {
    "workflow_key": "ownership",
    "name": "בעלות",
    "status": "completed",
    "summary": "נמצאה בעלות",
    "facts": ["דנה היא הבעלים"],
    "warnings": [],
}


class _SkillRepository:
    @staticmethod
    def published_content(_key, fallback):
        return fallback


def test_each_selected_skill_runs_in_its_own_call_with_its_full_instructions():
    """A Skill's own guidance must reach the model as the system prompt of a
    dedicated call, not share one call with the other Skills."""
    class FakeLlm:
        def __init__(self):
            self.systems = []

        def complete_json(self, system, _user, schema):
            self.systems.append(system)
            if "skill_results" in schema["properties"]:
                return {
                    "summary": "סיכום",
                    "key_findings": ["עובדה"],
                    "risks": [],
                    "missing_data": [],
                    "suggested_questions": [],
                    "skill_results": [],
                }
            return {
                "summary": "מה עושים עכשיו",
                "items": ["בדקו את הרשומה"],
                "sources": ["בעלות", "מקור מומצא"],
            }

    llm = FakeLlm()
    service = SummaryService(_SkillRepository(), None, llm, None)
    skills = [{
        "content_key": "summary-actions",
        "name": "צעדים מומלצים",
        "description": "פעולות ברורות",
        "content": "הצע רק פעולות המבוססות על עובדות.",
    }]
    result = service._final_summary("", "", [_OWNERSHIP_SECTION], skills)

    # One shared synthesis call plus one dedicated call for the Skill.
    assert len(llm.systems) == 2
    assert llm.systems[1].startswith("הצע רק פעולות המבוססות על עובדות.")
    # The invented source is dropped; the real section name survives.
    assert result["skill_results"] == [{
        "skill_key": "summary-actions",
        "name": "צעדים מומלצים",
        "summary": "מה עושים עכשיו",
        "items": ["בדקו את הרשומה"],
        "sources": ["בעלות"],
    }]


def test_one_failing_skill_does_not_discard_another_skills_result():
    class FakeLlm:
        def complete_json(self, system, _user, schema):
            if "skill_results" in schema["properties"]:
                return {
                    "summary": "סיכום",
                    "key_findings": [],
                    "risks": [],
                    "missing_data": [],
                    "suggested_questions": [],
                    "skill_results": [],
                }
            if system.startswith("נפילה"):
                raise AgentError("המודל לא זמין")
            return {"summary": "עבד", "items": [], "sources": []}

    service = SummaryService(_SkillRepository(), None, FakeLlm(), None)
    skills = [
        {
            "content_key": "broken",
            "name": "סקיל נופל",
            "content": "נפילה מכוונת.",
        },
        {
            "content_key": "working",
            "name": "סקיל עובד",
            "content": "עבודה רגילה.",
        },
    ]
    result = service._final_summary("", "", [_OWNERSHIP_SECTION], skills)

    # Order follows the user's selection, not completion order.
    assert [item["skill_key"] for item in result["skill_results"]] == [
        "broken", "working",
    ]
    assert "המודל לא זמין" in result["skill_results"][0]["summary"]
    assert result["skill_results"][1]["summary"] == "עבד"


def test_skill_preview_reports_invented_sources_without_persisting():
    """An FDE testing a Skill must see which citations were rejected, which is
    the signal a full summary run hides."""
    class FakeLlm:
        def complete_json(self, _system, _user, _schema):
            return {
                "summary": "טיוטה",
                "items": ["נקודה"],
                "sources": ["בעלות", "מקור מומצא"],
            }

    service = SummaryService(None, None, FakeLlm(), None)
    preview = service.preview_skill(
        "טיוטת Skill",
        "הצע רק פעולות המבוססות על עובדות.",
        "מה חשוב לדעת?",
        [{
            "workflow_key": "ownership",
            "name": "בעלות",
            "status": "completed",
            "summary": "נמצאה בעלות",
            "facts": ["דנה היא הבעלים"],
            "warnings": [],
        }],
    )

    assert preview["result"]["sources"] == ["בעלות"]
    assert preview["dropped_sources"] == ["מקור מומצא"]
    # The internal citation record never leaks to a caller.
    assert "_raw_sources" not in preview["result"]


def test_skill_results_never_expose_the_internal_citation_record():
    class FakeLlm:
        def complete_json(self, _system, _user, schema):
            if "skill_results" in schema["properties"]:
                return {
                    "summary": "סיכום",
                    "key_findings": [],
                    "risks": [],
                    "missing_data": [],
                    "suggested_questions": [],
                    "skill_results": [],
                }
            return {"summary": "עבד", "items": [], "sources": ["בדוי"]}

    service = SummaryService(_SkillRepository(), None, FakeLlm(), None)
    result = service._final_summary("", "", [_OWNERSHIP_SECTION], [{
        "content_key": "working",
        "name": "סקיל עובד",
        "content": "הנחיות.",
    }])

    assert result["skill_results"][0]["sources"] == []
    assert "_raw_sources" not in result["skill_results"][0]


def test_skill_preview_requires_instructions_and_sections():
    section = SkillPreviewSection(name="בעלות")

    with pytest.raises(ValidationError, match="נדרשות הנחיות"):
        SkillPreview(content="   ", sections=[section])

    with pytest.raises(ValidationError, match="חלק סיכום אחד"):
        SkillPreview(content="הנחיות", sections=[])


def test_summary_request_limits_and_deduplicates_skills():
    request = SummaryCreate(
        root_id="001",
        skill_keys=["summary-actions", "summary-actions", "summary-risks"],
    )

    assert request.skill_keys == ["summary-actions", "summary-risks"]

    with pytest.raises(ValueError, match="עד 3"):
        SummaryCreate(
            root_id="001",
            skill_keys=["one", "two", "three", "four"],
        )


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
        "output_schema": {
            "properties": {"risk_level": {"type": "string"}}
        },
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
        "owner_id", "owner_name", "risk_level",
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

    def execute(
        _run, _root_id, _question, workflows, _progress, _skills=None,
        _boundaries=None,
    ):
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


def test_fetch_one_id_infers_the_tool_output_schema():
    class FakeProvider:
        calls = []

        def run(self, _package, identifiers):
            self.calls.append(identifiers)
            return [
                {
                    "owner_id": "001",
                    "score": 1,
                    "active": True,
                    "_package_query": "internal",
                },
                {"owner_id": "002", "score": 1.5, "note": None},
            ]

    provider = FakeProvider()
    service = SummaryService(None, provider, None, None)
    result = service.inspect_tool({
        "name": "בעלות",
        "input_mode": "single",
    }, "001")

    assert provider.calls == [["001"]]
    assert result["row_count"] == 2
    assert result["truncated"] is False
    schema = result["output_schema"]
    assert schema["properties"]["owner_id"]["type"] == "string"
    assert schema["properties"]["score"]["type"] == "number"
    assert schema["properties"]["active"]["type"] == "boolean"
    assert schema["properties"]["note"]["type"] == "null"
    assert "_package_query" not in schema["properties"]
    assert schema["required"] == ["owner_id", "score"]


def test_fetch_one_id_generates_editable_tool_metadata_from_bounded_sample():
    class FakeProvider:
        @staticmethod
        def run(_package, _identifiers):
            return [
                {"owner_id": "001", "owner_name": "דנה"},
                {"owner_id": "002", "owner_name": "יוסי"},
            ]

    class FakeLlm:
        payload = None

        def complete_json(self, _system, user, _schema):
            self.payload = json.loads(user)
            return {
                "description": "מידע על בעלי הנכס ומזהיהם.",
                "agent_instructions": "סכם את שמות הבעלים.",
                "field_descriptions": {
                    "owner_id": "מזהה בעלים",
                    "owner_name": "שם הבעלים",
                    "invented": "לא קיים",
                },
            }

    llm = FakeLlm()
    service = SummaryService(None, FakeProvider(), llm, None)
    result = service.inspect_tool({
        "name": "בעלות",
        "package_id": "ownership",
        "input_cube_parameter": "identifier",
        "output_cube_name": "owners",
        "input_mode": "single",
        "output_schema": {
            "properties": {
                "owner_id": {
                    "type": "string",
                    "description": "תיאור ידני",
                    "x-summary": False,
                },
            },
        },
    }, "001")

    assert llm.payload["sample_data"] == [
        {"owner_id": "001", "owner_name": "דנה"},
        {"owner_id": "002", "owner_name": "יוסי"},
    ]
    assert result["metadata_suggestions"] == {
        "description": "מידע על בעלי הנכס ומזהיהם.",
        "agent_instructions": "סכם את שמות הבעלים.",
    }
    fields = result["output_schema"]["properties"]
    assert fields["owner_id"]["description"] == "תיאור ידני"
    assert fields["owner_id"]["x-summary"] is False
    assert fields["owner_name"]["description"] == "שם הבעלים"
    assert fields["owner_name"]["x-summary"] is True
    assert "invented" not in fields


def test_ignored_tool_fields_stay_in_evidence_but_not_summary_prompt():
    captured = {"evidence": None, "summary_payload": None}
    package = {
        "id": "tool-v1",
        "input_mode": "single",
        "output_schema": {
            "properties": {
                "owner_name": {"type": "string", "x-summary": True},
                "internal_code": {"type": "string", "x-summary": False},
            },
        },
    }

    class FakeRepository:
        @staticmethod
        def get_package(_version_id):
            return package

        @staticmethod
        def save_evidence(_run_id, _workflow_id, _step_key, records):
            captured["evidence"] = records
            return "evidence-1"

    class FakeProvider:
        @staticmethod
        def run(_package, _identifiers):
            return [{"owner_name": "דנה", "internal_code": "SECRET"}]

    class FakeLlm:
        @staticmethod
        def complete_json(_system, user, _schema):
            captured["summary_payload"] = json.loads(user)
            return {
                "summary": "דנה היא הבעלים.",
                "facts": ["דנה היא הבעלים"],
                "warnings": [],
                "suggested_questions": [],
            }

    service = SummaryService(
        FakeRepository(), FakeProvider(), FakeLlm(), None
    )
    result = service._execute_workflow(
        {"id": "run-1"}, "001", {
            "id": "workflow-v1",
            "workflow_key": "ownership",
            "name": "בעלות",
            "system_prompt": "",
            "output_schema": {},
            "steps": [{
                "key": "owners", "name": "בעלים",
                "package_version_id": "tool-v1", "depends_on": [],
                "input_source": "workflow.id", "input_field": "",
                "summary_prompt": "",
            }],
        },
    )

    assert captured["evidence"] == [{
        "owner_name": "דנה", "internal_code": "SECRET",
    }]
    fact = captured["summary_payload"]["facts"][0]
    assert fact["fields"] == ["owner_name"]
    assert fact["samples"] == {"owner_name": ["דנה"]}
    assert result["summary"] == "דנה היא הבעלים."


@pytest.mark.parametrize("pasted", [
    "http://ollama:11434/v1/chat/completions",
    "http://ollama:11434/v1/completions",
    "http://ollama:11434/v1/models",
    "http://ollama:11434/v1/",
])
def test_llm_base_url_strips_pasted_endpoint_suffixes(pasted):
    """The SDK appends the operation path itself, so a pasted endpoint
    would otherwise produce /v1/chat/completions/chat/completions."""
    assert normalize_llm_base_url(pasted) == "http://ollama:11434/v1"


def test_llm_base_url_requires_an_http_scheme():
    with pytest.raises(ValueError):
        normalize_llm_base_url("ollama:11434/v1")


def test_database_url_accepts_and_converts_jdbc_prefix():
    assert normalize_database_url(
        "jdbc:postgresql://db:5432/summaries"
    ) == "postgresql://db:5432/summaries"


def test_database_url_rejects_non_postgres_schemes():
    with pytest.raises(ValueError):
        normalize_database_url("mysql://db:3306/summaries")


def test_jdbc_current_schema_is_translated_for_libpq():
    """libpq rejects the currentSchema keyword outright, so a working JDBC
    string would fail to connect at all unless it is rewritten."""
    assert normalize_database_url(
        "jdbc:postgresql://db:5432/summaries?currentSchema=aisummry"
    ) == "postgresql://db:5432/summaries?options=-csearch_path%3Daisummry"


def test_current_schema_is_translated_alongside_other_parameters():
    converted = normalize_database_url(
        "postgresql://db:5432/summaries?currentSchema=aisummry&sslmode=require"
    )
    assert "currentSchema" not in converted
    assert "options=-csearch_path%3Daisummry" in converted
    assert "sslmode=require" in converted
    assert "?&" not in converted


def test_url_schema_is_extracted_for_the_schema_setting():
    assert extract_url_schema(
        "jdbc:postgresql://db:5432/summaries?currentSchema=reporting"
    ) == "reporting"
    assert extract_url_schema("postgresql://db:5432/summaries") == ""


def test_schema_name_must_be_a_plain_identifier():
    """The schema is interpolated into SET search_path, so anything other
    than an identifier must be refused."""
    assert normalize_database_schema(" aisummry ") == "aisummry"
    assert normalize_database_schema("") == ""
    for bad in ("evil; DROP TABLE x", "a-b", "1abc", 'x"y'):
        with pytest.raises(ValueError):
            normalize_database_schema(bad)


def test_jdbc_url_from_the_environment_is_normalized_at_boot(tmp_path):
    """Normalization used to run only on UI edits, so a jdbc: URL supplied
    through the environment reached libpq unconverted and failed."""
    store = RuntimeSettingsStore(Settings(
        runtime_settings_file=str(tmp_path / "runtime-settings.json"),
        database_url="jdbc:postgresql://db:5432/summaries?currentSchema=aisummry",
    ))
    settings = store.get()
    assert settings.database_url.startswith("postgresql://")
    assert "currentSchema" not in settings.database_url
    assert settings.database_schema == "aisummry"


def test_a_pasted_jdbc_url_sets_the_schema_from_the_ui(tmp_path):
    store = _store(tmp_path)
    updated = store.update({
        "database_url": "jdbc:postgresql://db:5432/summaries?currentSchema=reporting",
    })
    assert updated.database_schema == "reporting"


def test_an_explicit_schema_wins_over_the_one_in_the_url(tmp_path):
    store = _store(tmp_path)
    updated = store.update({
        "database_url": "postgresql://db:5432/summaries?currentSchema=fromurl",
        "database_schema": "explicit",
    })
    assert updated.database_schema == "explicit"


def test_an_invalid_environment_schema_does_not_prevent_boot(tmp_path):
    store = RuntimeSettingsStore(Settings(
        runtime_settings_file=str(tmp_path / "runtime-settings.json"),
        database_schema="evil; DROP TABLE x",
    ))
    assert store.get().database_schema == ""


def _store(tmp_path):
    return RuntimeSettingsStore(
        Settings(runtime_settings_file=str(tmp_path / "runtime-settings.json"))
    )


def test_clearing_a_nullable_setting_unsets_it(tmp_path):
    """An emptied base URL means "use the default OpenAI host", so it must
    become None rather than being skipped as a no-op update."""
    store = _store(tmp_path)
    store.update({"llm_base_url": "http://gateway/v1"})
    assert store.update({"llm_base_url": ""}).llm_base_url is None
    assert store.update({"database_port": None}).database_port is None


def test_masked_secret_does_not_overwrite_the_stored_value(tmp_path):
    store = _store(tmp_path)
    store.update({"openai_api_key": "real-key"})
    assert store.update({"openai_api_key": "********"}).openai_api_key == "real-key"
    assert store.public()["openai_api_key"] == "********"


def test_model_probe_prefers_typed_values_over_saved_ones():
    """The settings panel checks a connection BEFORE saving it, so what the
    user typed must reach list_models. A secret left masked is not a typed
    value — it has to fall back to the stored key."""
    body = ModelsProbeRequest(
        llm_base_url=" http://ollama:11434/v1 ", openai_api_key="sk-typed",
    )
    assert body.override("llm_base_url") == "http://ollama:11434/v1"
    assert body.override("openai_api_key") == "sk-typed"

    masked = ModelsProbeRequest(llm_base_url="", openai_api_key="********")
    assert masked.override("llm_base_url") is None
    assert masked.override("openai_api_key") is None
    assert ModelsProbeRequest().override("llm_base_url") is None


def test_saved_settings_survive_a_restart(tmp_path):
    _store(tmp_path).update({"llm_model": "gemma4:31b-cloud-v2"})
    assert _store(tmp_path).get().llm_model == "gemma4:31b-cloud-v2"


def test_invalid_saved_value_does_not_prevent_boot(tmp_path):
    path = tmp_path / "runtime-settings.json"
    store = _store(tmp_path)
    saved = json.loads(path.read_text("utf-8"))
    saved["database_url"] = "mysql://nope"
    path.write_text(json.dumps(saved), encoding="utf-8")
    assert _store(tmp_path).get().database_url == store.get().database_url


_TOOL_DRAFT_KEYS = (
    "name", "package_id", "input_cube_name", "input_cube_parameter",
    "output_cube_name", "input_mode", "description", "agent_instructions",
)


def _tool_answer(**overrides):
    answer = {
        "reply": "", "question": None, "resolved": [], "open_points": [],
        "awaiting_confirmation": False, "ready": False,
        "needs_inspection": False,
        "draft": {key: "" for key in _TOOL_DRAFT_KEYS},
    }
    answer.update(overrides)
    return answer


def _workflow_answer(**overrides):
    answer = {
        "reply": "", "question": None, "resolved": [], "open_points": [],
        "awaiting_confirmation": False, "ready": False,
        "draft": {
            "name": "", "description": "", "role": "detail", "rationale": "",
            "system_prompt": "", "steps": [], "missing_tools": [],
        },
    }
    answer.update(overrides)
    return answer


def _chat_service(answer, tools=None):
    """A service whose model returns one canned interview turn."""
    class FakeRepository:
        @staticmethod
        def list_packages():
            return list(tools or [])

    class FakeLlm:
        payload = None
        system = None

        @staticmethod
        def complete_json(system, user, _schema):
            FakeLlm.payload = json.loads(user)
            FakeLlm.system = system
            return answer

    return SummaryService(FakeRepository(), None, FakeLlm(), None), FakeLlm


def test_an_open_question_keeps_the_draft_out_of_the_form():
    """The interview does not act before the FDE answers, so a turn that
    still asks something is never ready however the model labelled it."""
    service, _llm = _chat_service(_tool_answer(
        reply="נשאר דבר אחד",
        question={
            "question": "החבילה מקבלת מזהה אחד או רשימה?",
            "recommendation": "single",
            "why": "many על חבילה שמצפה למזהה בודד נכשלת בשקט.",
        },
        ready=True,
    ))
    result = service.plan_tool_chat(
        [{"role": "fde", "text": "יש לי נתוני בעלות"}], {}, {},
    )

    assert result["ready"] is False
    assert result["question"]["recommendation"] == "single"


def test_a_summary_awaiting_confirmation_is_not_yet_ready():
    """Presenting the agreed summary is the ask for confirmation, not the
    confirmation itself; the draft unlocks only on the turn after."""
    service, _llm = _chat_service(_tool_answer(
        reply="סיכמנו: …", awaiting_confirmation=True, ready=True,
    ))
    result = service.plan_tool_chat(
        [{"role": "fde", "text": "סיימנו"}], {}, {},
    )

    assert result["awaiting_confirmation"] is True
    assert result["ready"] is False


def test_the_interview_cannot_rewrite_the_connection_the_fde_established():
    """The FDE typed the connection and a real run confirmed it, but the
    schema still makes the model echo it back. A model that paraphrases a cube
    name into Hebrew would replace a FLAPI identifier with a display label,
    and FLAPI answers that with an opaque server error far from here.
    """
    agreed = {
        "package_id": "PKG-IDENTITY",
        "input_cube_name": "entity_cube",
        "input_cube_parameter": "entity_id",
        "output_cube_name": "entity_details",
        "package_key": "identity",
        "query_name": "identity_lookup",
    }
    service, _llm = _chat_service(_tool_answer(draft=dict(
        {key: "" for key in _TOOL_DRAFT_KEYS},
        name="פרטי ישות",
        # The model paraphrasing the connection into Hebrew display text.
        package_id="חבילת זיהוי",
        input_cube_name="קוביית ישויות",
        input_cube_parameter="מזהה ישות",
        output_cube_name="פרטי הישות",
        package_key="זיהוי",
        query_name="חיפוש זיהוי",
    )))

    result = service.plan_tool_chat(
        [{"role": "fde", "text": "נמשיך"}], agreed, {},
    )

    for field, established in agreed.items():
        assert result["draft"][field] == established
    # What the interview genuinely owns still comes from this turn.
    assert result["draft"]["name"] == "פרטי ישות"


def test_the_interview_still_fills_a_connection_field_the_fde_left_empty():
    """Precedence protects what the FDE established; it must not freeze an
    empty field, or a draft opened from scratch could never be filled."""
    service, _llm = _chat_service(_tool_answer(draft=dict(
        {key: "" for key in _TOOL_DRAFT_KEYS},
        query_name="identity_lookup",
    )))

    result = service.plan_tool_chat(
        [{"role": "fde", "text": "נמשיך"}], {"query_name": ""}, {},
    )

    assert result["draft"]["query_name"] == "identity_lookup"


def test_a_turn_that_both_asks_and_claims_confirmation_is_still_asking():
    service, _llm = _chat_service(_tool_answer(
        question={
            "question": "מה שם הקובייה היוצאת?",
            "recommendation": "", "why": "",
        },
        awaiting_confirmation=True,
    ))
    result = service.plan_tool_chat(
        [{"role": "fde", "text": "נמשיך"}], {}, {},
    )

    assert result["awaiting_confirmation"] is False
    assert result["question"] is not None


def test_tool_chat_carries_earlier_answers_into_the_next_draft():
    # The model returns only what it learned this turn; everything the FDE
    # already supplied must survive rather than reset to empty.
    service, _llm = _chat_service(_tool_answer(
        draft=dict(
            {key: "" for key in _TOOL_DRAFT_KEYS}, output_cube_name="OUT",
        ),
    ))
    result = service.plan_tool_chat(
        [{"role": "fde", "text": "יש לי נתוני בעלות"}],
        {"name": "בעלות", "package_id": "PKG-1", "input_mode": "single"},
        {},
    )

    assert result["draft"]["name"] == "בעלות"
    assert result["draft"]["package_id"] == "PKG-1"
    assert result["draft"]["input_mode"] == "single"
    assert result["draft"]["output_cube_name"] == "OUT"


def test_tool_chat_passes_only_bounded_sample_data_to_the_model():
    service, llm = _chat_service(_tool_answer())
    service.plan_tool_chat(
        [{"role": "fde", "text": "הרצתי Fetch 1 ID"}],
        {},
        {
            "row_count": 3,
            "records": [
                {"parcel_id": "00123", "_internal": "secret", "owner": "דנה"}
                for _index in range(40)
            ],
            "output_schema": {"properties": {"parcel_id": {}}},
        },
    )

    sample = llm.payload["inspection_result"]["sample_data"]
    assert len(sample) == 25
    # Underscore-prefixed internals never reach the model.
    assert all("_internal" not in row for row in sample)
    # A leading zero survives the trip to the model as a string.
    assert sample[0]["parcel_id"] == "00123"


def test_an_unusable_input_mode_falls_back_to_the_one_already_agreed():
    """`single`/`many` is the field that fails silently when wrong, and the FDE
    sets it on the form before the interview opens. A junk value from the model
    must not blank what they chose."""
    service, _llm = _chat_service(_tool_answer(
        draft=dict({key: "" for key in _TOOL_DRAFT_KEYS}, input_mode="batch"),
    ))
    result = service.plan_tool_chat(
        [{"role": "fde", "text": "נמשיך"}], {"input_mode": "many"}, {},
    )

    assert result["draft"]["input_mode"] == "many"


def test_the_connection_the_fde_supplied_survives_a_turn_that_omits_it():
    """The FDE fills the connection and proves it with a real run before the
    interview starts, so it is carried, never re-proposed."""
    service, _llm = _chat_service(_tool_answer(
        draft={key: "" for key in _TOOL_DRAFT_KEYS},
    ))
    result = service.plan_tool_chat(
        [{"role": "fde", "text": "ראית את הפלט"}],
        {
            "package_id": "PKG-7", "input_cube_name": "IN",
            "input_cube_parameter": "parcel_id", "output_cube_name": "OUT",
        },
        {},
    )

    assert result["draft"]["package_id"] == "PKG-7"
    assert result["draft"]["input_cube_parameter"] == "parcel_id"
    assert result["draft"]["output_cube_name"] == "OUT"


def test_the_interview_never_re_asks_what_the_history_already_answered():
    """Facts are looked up, not asked: the whole history reaches the model so
    it can read prior answers instead of repeating the question."""
    service, llm = _chat_service(_tool_answer())
    service.plan_tool_chat(
        [
            {"role": "fde", "text": "החבילה היא OWN-1"},
            {"role": "agent", "text": "מה מצב הקלט?"},
            {"role": "fde", "text": "single"},
        ],
        {}, {},
    )

    said = [turn["text"] for turn in llm.payload["conversation"]]
    assert said == ["החבילה היא OWN-1", "מה מצב הקלט?", "single"]


def test_workflow_chat_rejects_a_draft_naming_a_tool_outside_the_catalog():
    service, _llm = _chat_service(
        _workflow_answer(
            ready=True,
            draft={
                "name": "תמונת בעלות", "description": "", "role": "baseline",
                "rationale": "", "system_prompt": "",
                "steps": [{
                    "key": "ownership", "name": "בעלות",
                    "package_version_id": "does-not-exist",
                    "depends_on": [], "input_source": "workflow.id",
                    "input_field": "", "summary_prompt": "",
                }],
                "missing_tools": [],
            },
        ),
        tools=[{
            "id": "pkg-real", "name": "בעלות", "input_mode": "single",
            "input_cube_parameter": "id", "output_schema": {},
        }],
    )
    result = service.plan_workflow_chat(
        [{"role": "fde", "text": "בנה לי תהליך"}], {}
    )

    # The model claimed ready; the shared validation gate overrules it.
    assert result["ready"] is False
    assert result["draft"]["can_build"] is False
    assert result["draft"]["steps"] == []
    assert result["draft"]["missing_tools"]


def test_workflow_chat_rejects_a_step_reading_an_undeclared_dependency():
    service, _llm = _chat_service(
        _workflow_answer(
            ready=True,
            draft={
                "name": "שרשרת", "description": "", "role": "detail",
                "rationale": "", "system_prompt": "",
                "steps": [
                    {
                        "key": "first", "name": "ראשון",
                        "package_version_id": "pkg-real", "depends_on": [],
                        "input_source": "workflow.id", "input_field": "",
                        "summary_prompt": "",
                    },
                    {
                        "key": "second", "name": "שני",
                        "package_version_id": "pkg-real", "depends_on": [],
                        "input_source": "steps.first",
                        "input_field": "parcel_id", "summary_prompt": "",
                    },
                ],
                "missing_tools": [],
            },
        ),
        tools=[{
            "id": "pkg-real", "name": "בעלות", "input_mode": "single",
            "input_cube_parameter": "id", "output_schema": {},
        }],
    )
    result = service.plan_workflow_chat(
        [{"role": "fde", "text": "שרשר שני שלבים"}], {}
    )

    assert result["ready"] is False
    assert result["draft"]["can_build"] is False


def test_a_confirmed_workflow_keeps_the_route_the_model_stopped_repeating():
    """The plan is rebuilt from the model's answer every turn, so a
    confirmation turn that replies without re-emitting the steps must not drop
    the route. That turn is exactly when `ready` becomes true, and an empty
    `steps` there leaves `can_build` false — the FDE agrees to a plan and the
    canvas then refuses to load it."""
    agreed = [{
        "key": "ownership", "name": "בעלות",
        "package_version_id": "pkg-real", "depends_on": [],
        "input_source": "workflow.id", "input_field": "",
        "summary_prompt": "",
    }]
    service, _llm = _chat_service(
        _workflow_answer(
            ready=True,
            reply="מאשר, זה המסלול.",
            draft={
                "name": "", "description": "", "role": "detail",
                "rationale": "", "system_prompt": "",
                "steps": [], "missing_tools": [],
            },
        ),
        tools=[{
            "id": "pkg-real", "name": "בעלות", "input_mode": "single",
            "input_cube_parameter": "id", "output_schema": {},
        }],
    )
    result = service.plan_workflow_chat(
        [{"role": "fde", "text": "מאשר"}],
        {"name": "תמונת בעלות", "role": "baseline", "steps": agreed},
    )

    assert result["draft"]["steps"] == agreed
    assert result["draft"]["can_build"] is True
    assert result["draft"]["name"] == "תמונת בעלות"
    assert result["ready"] is True


def test_a_workflow_turn_that_revises_the_route_replaces_it():
    """Carrying the last turn forward must not freeze it: a turn that does
    send steps is the FDE and agent changing their minds, and it wins."""
    revised = [{
        "key": "permits", "name": "היתרים",
        "package_version_id": "pkg-real", "depends_on": [],
        "input_source": "workflow.id", "input_field": "",
        "summary_prompt": "",
    }]
    service, _llm = _chat_service(
        _workflow_answer(draft={
            "name": "", "description": "", "role": "detail", "rationale": "",
            "system_prompt": "", "steps": revised, "missing_tools": [],
        }),
        tools=[{
            "id": "pkg-real", "name": "בעלות", "input_mode": "single",
            "input_cube_parameter": "id", "output_schema": {},
        }],
    )
    result = service.plan_workflow_chat(
        [{"role": "fde", "text": "תחליף להיתרים"}],
        {"steps": [{
            "key": "ownership", "name": "בעלות",
            "package_version_id": "pkg-real", "depends_on": [],
            "input_source": "workflow.id", "input_field": "",
            "summary_prompt": "",
        }]},
    )

    assert result["draft"]["steps"] == revised


def test_the_interview_shows_the_output_fields_it_can_ask_about():
    """The wiring question names real fields, so the catalog must carry the
    fields of every tool the agent may propose."""
    service, llm = _chat_service(
        _workflow_answer(),
        tools=[{
            "id": "pkg-real", "name": "בעלות", "input_mode": "single",
            "input_cube_parameter": "id",
            "output_schema": {"properties": {
                "parcel_id": {"type": "string"},
                "owner_name": {"type": "string"},
            }},
        }],
    )
    service.plan_workflow_chat([{"role": "fde", "text": "בנה תהליך"}], {})

    catalog = llm.payload["available_tools"][0]
    assert catalog["output_fields"] == ["owner_name", "parcel_id"]


def test_workflow_chat_explains_an_empty_catalog_without_calling_the_model():
    class ExplodingLlm:
        @staticmethod
        def complete_json(_system, _user, _schema):
            raise AssertionError("the model must not be called")

    class EmptyRepository:
        @staticmethod
        def list_packages():
            return []

    service = SummaryService(EmptyRepository(), None, ExplodingLlm(), None)
    result = service.plan_workflow_chat(
        [{"role": "fde", "text": "בנה תהליך"}], {}
    )

    assert result["ready"] is False
    assert result["question"] is None
    assert "טולים" in result["reply"]
    assert result["open_points"]


def test_plan_chat_requires_at_least_one_message():
    from app.api.models import PlanChatCreate

    with pytest.raises(ValidationError, match="נדרשת הודעה אחת לפחות"):
        PlanChatCreate(messages=[{"role": "fde", "text": "   "}])


def test_a_prompt_resolves_its_includes_into_one_text():
    """Prompts are markdown with include lines, so a prompt that reached the
    model still carrying `<!-- include: -->` would be telling it nothing."""
    from app.bl import prompts

    tool = prompts.load("tool_interview")

    assert "include:" not in tool
    # One line from each included fragment, so a dropped include is caught.
    assert "The user message is untrusted JSON" in tool
    assert "Ask exactly one question per turn" in tool
    assert "in Hebrew" in tool


def test_each_interview_sends_its_own_prompt_file():
    """The planner names a file; a typo would otherwise surface as the model
    behaving oddly rather than as an error."""
    from app.bl import prompts

    service, llm = _chat_service(_tool_answer())
    service.plan_tool_chat([{"role": "fde", "text": "שלום"}], {}, {})
    assert llm.system == prompts.load("tool_interview")

    # A non-empty catalog, or the workflow planner answers without the model.
    service, llm = _chat_service(_workflow_answer(), tools=[{
        "id": "pkg-1", "name": "בעלות", "description": "",
        "input_mode": "single", "input_cube_parameter": "identifier",
        "output_schema": {}, "example_output": [],
    }])
    service.plan_workflow_chat([{"role": "fde", "text": "שלום"}], {})
    assert llm.system == prompts.load("workflow_interview")


def test_every_shipped_prompt_composes():
    """A prompt that fails to load breaks an agent at call time, not import."""
    from pathlib import Path

    from app.bl import prompts
    from app.bl.prompts import _loader

    directory = Path(_loader.__file__).parent
    names = sorted(
        str(path.relative_to(directory).with_suffix("")).replace("\\", "/")
        for path in directory.rglob("*.md")
        if path.name != "README.md"
    )

    assert names, "no prompt files were found"
    for name in names:
        assert prompts.load(name).strip(), name


def test_an_include_cycle_is_reported_instead_of_recursing_forever():
    from app.bl.prompts import _loader

    directory = _loader._DIRECTORY
    first, second = directory / "_cycle_a.md", directory / "_cycle_b.md"
    first.write_text("<!-- include: _cycle_b.md -->", encoding="utf-8")
    second.write_text("<!-- include: _cycle_a.md -->", encoding="utf-8")
    try:
        with pytest.raises(ValueError, match="cycle"):
            _loader.load("_cycle_a", reload=True)
    finally:
        first.unlink()
        second.unlink()
        _loader.clear_cache()


def test_reload_picks_up_an_edit_without_a_restart():
    """The reason prompts are files: wording iterates without a restart."""
    from app.bl.prompts import _loader

    path = _loader._DIRECTORY / "_reload_probe.md"
    path.write_text("first", encoding="utf-8")
    try:
        assert _loader.load("_reload_probe") == "first"
        path.write_text("second", encoding="utf-8")
        assert _loader.load("_reload_probe") == "first"  # cached
        assert _loader.load("_reload_probe", reload=True) == "second"
    finally:
        path.unlink()
        _loader.clear_cache()


def test_fact_chunks_keep_whole_rows_so_values_stay_correlated():
    """Grouping values per field destroyed which value belonged to which row.

    A summary cannot say "the open case is the 2023 one" from five names and
    five dates listed separately.
    """
    records = [
        {"case": "C-1", "state": "פתוח"},
        {"case": "C-2", "state": "סגור"},
    ]

    chunk = chunk_facts({"cases": records})[0]

    assert chunk["rows"] == records
    assert chunk["row_count"] == 2


def test_chunk_statistics_are_computed_over_every_row_not_a_sample():
    """Frequency is arithmetic, so it is derived in Python and cannot be
    hallucinated. This is what lets a section say "2 of 3"."""
    records = [{"state": "פתוח"}, {"state": "פתוח"}, {"state": "סגור"}]

    stats = chunk_facts({"cases": records})[0]["stats"]["state"]

    assert stats["counts"] == {"פתוח": 2, "סגור": 1}
    assert stats["present"] == 3
    assert stats["missing"] == 0
    assert stats["distinct"] == 2


def test_missing_values_are_counted_rather_than_silently_dropped():
    records = [{"department": "רישוי"}, {"department": None}, {}]

    stats = chunk_facts({"cases": records})[0]["stats"]["department"]

    assert stats["present"] == 1
    assert stats["missing"] == 2


def test_numeric_fields_report_range_and_mean():
    records = [{"amount": 10}, {"amount": 20}, {"amount": 30}]

    stats = chunk_facts({"cases": records})[0]["stats"]["amount"]

    assert (stats["min"], stats["max"], stats["mean"]) == (10.0, 30.0, 20.0)


def test_high_cardinality_fields_omit_counts_to_keep_the_payload_small():
    """Counting every value of an identifier column tells the model nothing
    and would bloat the prompt."""
    records = [{"case": "C-%d" % index} for index in range(40)]

    stats = chunk_facts({"cases": records})[0]["stats"]["case"]

    assert "counts" not in stats
    assert stats["distinct"] == 40


def test_summary_fields_policy_still_hides_internal_columns_from_rows():
    """`x-summary: false` must hold for the new row payload too, or a field
    kept out of the summary would leak through `rows`."""
    records = [{"owner_name": "דנה", "internal_code": "SECRET"}]

    chunk = chunk_facts({"owners": records}, {"owners": ["owner_name"]})[0]

    assert chunk["rows"] == [{"owner_name": "דנה"}]
    assert "internal_code" not in chunk["stats"]


def test_a_section_falling_back_is_marked_degraded_rather_than_looking_thin():
    """Without the flag a reader cannot tell "the model failed" from
    "there is little data", and wrongly concludes the latter."""
    class FailingLlm:
        @staticmethod
        def complete_json(_system, _user, _schema):
            raise AgentError("model unavailable")

    service = SummaryService(None, None, FailingLlm(), None)
    workflow = {"name": "בעלות", "system_prompt": "", "output_schema": {}}

    section = service._section_summary(
        workflow, [{"step": "owners", "row_count": 3}], []
    )

    assert section["degraded"] is True
    assert section["warnings"]


def _history_service(llm, turns, **repository_extras):
    """A service whose repository returns `turns` as conversation history."""
    class FakeRepository:
        @staticmethod
        def conversation_history(_conversation_id, _limit):
            return turns

        @staticmethod
        def published_content(_key, fallback):
            return fallback

        @staticmethod
        def published_workflows(_roles):
            return repository_extras.get("workflows", [])

        @staticmethod
        def agent_tools():
            return repository_extras.get("tools", [])

        @staticmethod
        def run_evidence(_run_id):
            return []

    return SummaryService(FakeRepository(), None, llm, None)


def test_an_opening_follow_up_is_routed_without_paying_for_a_rewrite():
    """With no prior turn there is nothing to resolve against, so spending an
    LLM call on every first follow-up would be pure cost."""
    class NeverCalledLlm:
        calls = 0

        def complete_json(self, _system, _user, _schema):
            self.calls += 1
            raise AssertionError("no rewrite should be attempted")

    llm = NeverCalledLlm()

    question = history.standalone_question(
        _history_service(llm, []), "מה מצב הנכס?", []
    )

    assert question == "מה מצב הנכס?"
    assert llm.calls == 0


def test_a_follow_up_is_restated_so_the_router_can_act_on_it():
    """"ולמה?" names its subject only by reference to the previous turn; a
    router given the raw text has nothing to select on."""
    turns = [{"question": "מה מצב הנכס?", "answer": "הנכס אינו פעיל."}]

    class RewritingLlm:
        received = None

        def complete_json(self, _system, user, _schema):
            self.received = json.loads(user)
            return {"question": "למה הנכס אינו פעיל?", "changed": True}

    llm = RewritingLlm()

    question = history.standalone_question(
        _history_service(llm, turns), "ולמה?", turns
    )

    assert question == "למה הנכס אינו פעיל?"
    assert llm.received["history"] == turns


def test_a_question_already_standing_alone_is_left_exactly_as_written():
    """`changed=false` is the model declining to rewrite. Honoring it keeps
    the user's own wording instead of a paraphrase of it."""
    turns = [{"question": "מה מצב הנכס?", "answer": "הנכס אינו פעיל."}]

    class DecliningLlm:
        @staticmethod
        def complete_json(_system, _user, _schema):
            return {"question": "משהו אחר לגמרי", "changed": False}

    question = history.standalone_question(
        _history_service(DecliningLlm(), turns), "מי הבעלים של 001?", turns
    )

    assert question == "מי הבעלים של 001?"


def test_a_failed_rewrite_routes_the_original_question_instead_of_failing():
    """The rewrite is an optimization for routing. A model that errors must
    leave the caller where it would have been without it, never worse."""
    turns = [{"question": "מה מצב הנכס?", "answer": "הנכס אינו פעיל."}]

    class FailingLlm:
        @staticmethod
        def complete_json(_system, _user, _schema):
            raise AgentError("model unavailable")

    question = history.standalone_question(
        _history_service(FailingLlm(), turns), "ולמה?", turns
    )

    assert question == "ולמה?"


def test_an_empty_rewrite_is_rejected_rather_than_routed_on():
    """A blank result means the model dropped the question rather than
    restating it, and routing on nothing is worse than routing on the text."""
    turns = [{"question": "מה מצב הנכס?", "answer": "הנכס אינו פעיל."}]

    class EmptyLlm:
        @staticmethod
        def complete_json(_system, _user, _schema):
            return {"question": "  ", "changed": True}

    question = history.standalone_question(
        _history_service(EmptyLlm(), turns), "ולמה?", turns
    )

    assert question == "ולמה?"


def test_the_router_is_shown_the_thread_so_it_can_resolve_a_reference():
    """Without history the router cannot tell a new request from a question
    about something it has already answered."""
    turns = [{"question": "מה מצב הנכס?", "answer": "הנכס אינו פעיל."}]

    class FakeLlm:
        received = None

        def complete_json(self, _system, user, _schema):
            self.received = json.loads(user)
            return {
                "action": "use_cached",
                "workflow_key": None,
                "tool_version_id": None,
                "clarification": None,
            }

    llm = FakeLlm()
    service = _history_service(llm, turns)

    service._select_detail(
        "למה הנכס אינו פעיל?",
        [{"workflow_key": "status", "name": "מצב", "description": "מצב הנכס"}],
        [{"step_key": "baseline", "records": [{"state": "לא פעיל"}]}],
        turns=turns,
    )

    assert llm.received["history"] == turns


def test_an_opening_request_sends_the_router_payload_it_always_did():
    """`history` is added only when there is a thread, so a first request is
    not changed by a feature that has nothing to contribute to it."""
    class FakeLlm:
        received = None

        def complete_json(self, _system, user, _schema):
            self.received = json.loads(user)
            return {
                "action": "use_cached",
                "workflow_key": None,
                "tool_version_id": None,
                "clarification": None,
            }

    llm = FakeLlm()
    service = _history_service(llm, [])

    service._select_detail(
        "מה מצב הנכס?",
        [{"workflow_key": "status", "name": "מצב", "description": "מצב הנכס"}],
        [{"step_key": "baseline", "records": [{"state": "לא פעיל"}]}],
    )

    assert "history" not in llm.received


def test_a_follow_up_run_keeps_the_users_wording_while_routing_on_the_rewrite():
    """What is persisted and shown must stay what the user typed; the
    rewrite is an internal routing aid, not a correction of the user."""
    turns = [{"question": "מה מצב הנכס?", "answer": "הנכס אינו פעיל."}]
    workflow = {
        "workflow_key": "status", "name": "מצב", "description": "מצב הנכס",
    }

    class RewritingLlm:
        @staticmethod
        def complete_json(_system, _user, _schema):
            return {"question": "למה הנכס אינו פעיל?", "changed": True}

    service = _history_service(
        RewritingLlm(), turns, workflows=[workflow]
    )
    service._select_detail = lambda *_args, **_kwargs: {
        "action": "workflow", "workflow_key": "status",
    }
    captured = {}

    def execute(
        _run, _root_id, question, _workflows, _progress, _skills=None,
        _boundaries=None,
    ):
        captured["question"] = question
        return {"summary": "ok"}

    service._execute = execute
    run = {"id": "run-9", "question": "ולמה?"}

    service.follow_up(
        run, {"id": "conv-1", "root_id": "001", "runs": []},
        lambda *_args: None,
    )

    assert captured["question"] == "למה הנכס אינו פעיל?"
    assert run["question"] == "ולמה?"


def test_a_repository_without_history_still_answers_follow_ups():
    """`conversation_history` is newer than the callers of `follow_up`; a
    fake or older repository lacking it must degrade, not crash."""
    class OlderRepository:
        @staticmethod
        def published_workflows(_roles):
            return []

        @staticmethod
        def agent_tools():
            return []

    turns = history.recent_turns(
        SummaryService(OlderRepository(), None, None, None),
        {"id": "conv-1"},
    )

    assert turns == []


def test_a_long_answer_is_clipped_before_it_crowds_out_the_evidence():
    """Prior answers are context for resolving a reference, not the payload
    the router selects on."""
    turns = history.recent_turns(
        _history_service(None, [
            {"question": "מה?", "answer": "א" * 5000},
        ]),
        {"id": "conv-1"},
    )

    assert len(turns[0]["answer"]) < 5000
    assert turns[0]["answer"].endswith("…")


def test_a_thread_title_breaks_between_words_rather_than_mid_word():
    """The title is shown in the history sidebar, where a word cut in half
    reads as corruption rather than as truncation."""
    title = conversation_title("מה " + "בעלות " * 40)

    assert len(title) <= 81
    assert title.endswith("…")
    assert "  " not in title


def _clarifying_service(selection, workflows=None, tools=None):
    """A service whose router returns `selection` for any question."""
    class FakeRepository:
        @staticmethod
        def published_workflows(_roles):
            return workflows or []

        @staticmethod
        def agent_tools():
            return tools or []

        @staticmethod
        def run_evidence(_run_id):
            return []

        @staticmethod
        def conversation_history(_conversation_id, _limit):
            return []

    service = SummaryService(FakeRepository(), None, None, None)
    service._select_detail = lambda *_args, **_kwargs: selection
    return service


def test_a_clarifying_question_offers_answers_rather_than_a_catalog():
    """Listing every workflow name asked the user to choose from an inventory
    they did not write; an option is an answer to the question asked."""
    service = _clarifying_service({
        "action": "clarify",
        "clarification": "מה מעניין אותך בנכס?",
        "recommendation": "הייתי מתחיל בבעלות.",
        "options": [
            {"label": "בעלות", "answer": "מי הבעלים של הנכס?"},
            {"label": "עסקאות", "answer": "אילו עסקאות בוצעו בנכס?"},
        ],
    })

    result = service.follow_up(
        {"id": "run-1", "question": "ספר לי עוד"},
        {"id": "conv-1", "root_id": "001", "runs": []},
        lambda *_args: None,
    )

    assert result["needs_clarification"] is True
    assert result["recommendation"] == "הייתי מתחיל בבעלות."
    assert [option["label"] for option in result["options"]] == [
        "בעלות", "עסקאות",
    ]
    # The clicked option is sent verbatim, so it must be a whole question.
    assert result["suggested_questions"] == [
        "מי הבעלים של הנכס?", "אילו עסקאות בוצעו בנכס?",
    ]


def test_a_lone_option_is_dropped_because_one_choice_is_not_a_choice():
    """A single-item menu sits beside a question that already says the same
    thing, so it costs a click without offering a decision."""
    service = _clarifying_service({
        "action": "clarify",
        "clarification": "מה מעניין אותך?",
        "options": [{"label": "בעלות", "answer": "מי הבעלים?"}],
    })

    result = service.follow_up(
        {"id": "run-1", "question": "ספר לי עוד"},
        {"id": "conv-1", "root_id": "001", "runs": []},
        lambda *_args: None,
    )

    assert result["options"] == []


def test_an_option_without_an_answer_is_dropped_rather_than_sending_its_label():
    """A label is a button caption. Sending it would put a fragment in the
    composer where a question belongs."""
    service = _clarifying_service({
        "action": "clarify",
        "clarification": "מה מעניין אותך?",
        "options": [
            {"label": "בעלות", "answer": "מי הבעלים?"},
            {"label": "עסקאות", "answer": ""},
            {"label": "שומה", "answer": "מה השומה?"},
        ],
    })

    result = service.follow_up(
        {"id": "run-1", "question": "ספר לי עוד"},
        {"id": "conv-1", "root_id": "001", "runs": []},
        lambda *_args: None,
    )

    assert [option["label"] for option in result["options"]] == [
        "בעלות", "שומה",
    ]


def test_a_clarification_without_options_still_names_what_is_available():
    """Something to click beats a dead end, so the catalog names remain the
    fallback when the router could not enumerate real answers."""
    workflow = {
        "workflow_key": "ownership", "name": "בעלות", "description": "בעלים",
    }
    service = _clarifying_service(
        {"action": "clarify", "clarification": "מה מעניין אותך?"},
        workflows=[workflow],
    )

    result = service.follow_up(
        {"id": "run-1", "question": "ספר לי עוד"},
        {"id": "conv-1", "root_id": "001", "runs": []},
        lambda *_args: None,
    )

    assert result["options"] == []
    assert result["suggested_questions"] == ["בעלות"]


def test_a_router_naming_an_unavailable_workflow_still_offers_the_real_ones():
    """A rejected selection is a dead end unless the user is given somewhere
    to go, and here the real alternatives are known exactly."""
    workflows = [
        {"workflow_key": "ownership", "name": "בעלות", "description": ""},
        {"workflow_key": "deals", "name": "עסקאות", "description": ""},
    ]

    class FakeLlm:
        @staticmethod
        def complete_json(_system, _user, _schema):
            return {
                "action": "workflow",
                "workflow_key": "does-not-exist",
                "tool_version_id": None,
                "clarification": None,
            }

    class FakeRepository:
        @staticmethod
        def published_content(_key, fallback):
            return fallback

    service = SummaryService(FakeRepository(), None, FakeLlm(), None)

    selected = service._select_detail("ספר לי עוד", workflows, [])

    assert selected["action"] == "clarify"
    assert [option["label"] for option in selected["options"]] == [
        "בעלות", "עסקאות",
    ]


def test_the_model_being_unavailable_still_offers_the_catalog_to_choose_from():
    """This is the no-model path, so the options are built in Python from the
    catalog rather than asked for."""
    workflows = [
        {"workflow_key": "ownership", "name": "בעלות", "description": ""},
        {"workflow_key": "deals", "name": "עסקאות", "description": ""},
    ]

    class FailingLlm:
        @staticmethod
        def complete_json(_system, _user, _schema):
            raise AgentError("model unavailable")

    class FakeRepository:
        @staticmethod
        def published_content(_key, fallback):
            return fallback

    service = SummaryService(FakeRepository(), None, FailingLlm(), None)

    selected = service._select_detail("ספר לי עוד", workflows, [])

    assert selected["action"] == "clarify"
    assert len(selected["options"]) == 2


class _EditableWorkflows(Repository):
    """Repository with the database removed, to exercise the edit rules.

    `update_workflow` is the operation that replaced append-only versioning,
    so what matters here is which SQL it decides to send — not that psycopg
    can send it.
    """

    def __init__(self, status, steps):
        self._store = None
        self._row = {
            "id": "wf", "workflow_key": "ownership", "name": "Ownership",
            "status": status, "steps": steps, "examples": [],
        }
        self.statements = []

    def get_workflow(self, workflow_id):
        return dict(self._row)

    def get_package(self, package_version_id):
        return {"name": "tool", "example_input": [], "example_output": []}


class _FakeConnection:
    def __init__(self, sink):
        self._sink = sink

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, query, params=()):
        self._sink.append(" ".join(str(query).split()))

    def commit(self):
        pass


def _capture_sql(monkeypatch, repository):
    monkeypatch.setattr(
        "app.dal.repository.workflows.connect",
        lambda _store: _FakeConnection(repository.statements),
    )


_STEP = {
    "key": "step1", "name": "S1", "package_version_id": "tool",
    "depends_on": [], "input_source": "workflow.id",
}


def test_editing_a_published_workflow_keeps_it_published(monkeypatch):
    """The bug this replaced: an edit appended a draft version that hid the
    published row still serving traffic, so a live workflow reported itself
    as unpublished."""
    repository = _EditableWorkflows("published", [_STEP])
    _capture_sql(monkeypatch, repository)

    repository.update_workflow(
        "wf", {"name": "Ownership", "steps": [_STEP], "examples": [{"a": 1}]}
    )

    update = next(s for s in repository.statements if s.startswith("UPDATE"))
    assert "status" not in update, "an edit must not change publication state"


def test_editing_a_published_workflow_cannot_break_it(monkeypatch):
    """A published workflow is live, so an edit clears the same bar publishing
    does rather than being demoted back to a draft."""
    repository = _EditableWorkflows("published", [_STEP])
    _capture_sql(monkeypatch, repository)

    with pytest.raises(ValueError, match="ללא שלבים"):
        repository.update_workflow("wf", {"name": "Ownership", "steps": []})

    assert not repository.statements, "nothing may be written when refused"


def test_editing_a_draft_workflow_skips_publish_validation(monkeypatch):
    """A draft is not answering requests, so it may be saved half-built."""
    repository = _EditableWorkflows("draft", [])
    _capture_sql(monkeypatch, repository)

    repository.update_workflow("wf", {"name": "Ownership", "steps": []})

    assert any(s.startswith("UPDATE") for s in repository.statements)


class _DeletableContent(Repository):
    """Repository with the database removed, to check what delete sends."""

    def __init__(self):
        self._store = None
        self.statements = []

    def _one(self, query, params=()):
        return {"content_key": "summary-executive", "name": "תקציר מנהלים"}


def test_deleting_a_skill_removes_the_row_it_was_given(monkeypatch):
    """Content is one row per key, so a delete targets the id it was handed —
    not the key, which would be the same statement by accident today and a
    silent multi-row delete the moment that stops being true."""
    repository = _DeletableContent()
    monkeypatch.setattr(
        "app.dal.repository.content.connect",
        lambda _store: _FakeConnection(repository.statements),
    )

    removed = repository.delete_agent_content("content-1")

    assert removed == {"deleted": "summary-executive", "name": "תקציר מנהלים"}
    assert repository.statements == ["DELETE FROM agent_content WHERE id=%s"]


def test_deleting_a_prompt_leaves_the_file_based_default(monkeypatch):
    """`published_content` falls back to the prompt under `bl/prompts/`, which
    is what makes deleting the planner prompt a reset rather than a break."""
    repository = _DeletableContent()
    monkeypatch.setattr(
        "app.dal.repository.content.connect",
        lambda _store: _FakeConnection(repository.statements),
    )
    monkeypatch.setattr(repository, "_all", lambda *_args, **_kwargs: [])

    repository.delete_agent_content("content-1")

    assert repository.published_content(
        "workflow-planner", "file default"
    ) == "file default"
