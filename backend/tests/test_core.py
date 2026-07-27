import json
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
from app.dal.repository.validation import step_levels
from app.api.validation_errors import format_validation_error
from app.bl.workflow_engine import _SECTION_SCHEMA, SummaryService
from app.api.models import (
    ModelsProbeRequest, SkillPreview, SkillPreviewSection, SummaryCreate,
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
