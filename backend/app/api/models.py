"""Pydantic contracts for the HTTP boundary."""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from app.common.runtime_settings.normalizers import MASKED_SECRET


class PackageCreate(BaseModel):
    package_key: Optional[str] = None
    name: str
    description: str = ""
    package_id: str
    input_cube_name: str
    input_cube_parameter: str
    input_mode: Literal["single", "many"] = "single"
    output_cube_name: str
    query_name: str = ""
    timeout_seconds: Optional[int] = None
    agent_enabled: bool = True
    agent_instructions: str = ""
    output_schema: Dict[str, Any] = Field(default_factory=dict)
    example_input: List[str] = Field(default_factory=list)
    example_output: List[Dict[str, Any]] = Field(default_factory=list)

    @field_validator(
        "name", "package_id", "input_cube_name",
        "input_cube_parameter", "output_cube_name",
    )
    @classmethod
    def required_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("שדה חובה")
        return cleaned


class WorkflowStep(BaseModel):
    key: str
    name: str
    package_version_id: str
    depends_on: List[str] = Field(default_factory=list)
    input_source: str = "workflow.id"
    input_field: str = ""
    summary_prompt: str = ""

    @field_validator("key")
    @classmethod
    def valid_key(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned or not cleaned.replace("-", "_").isalnum():
            raise ValueError("מפתח שלב חייב להכיל אותיות, מספרים, _ או -")
        return cleaned


class WorkflowCreate(BaseModel):
    workflow_key: Optional[str] = None
    name: str
    description: str = ""
    role: Literal["baseline", "detail", "both"] = "detail"
    system_prompt: str = ""
    output_schema: Dict[str, Any] = Field(default_factory=dict)
    examples: List[Dict[str, Any]] = Field(default_factory=list)
    steps: List[WorkflowStep] = Field(default_factory=list)


class WorkflowPlanCreate(BaseModel):
    prompt: str

    @field_validator("prompt")
    @classmethod
    def prompt_required(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("נדרשת הנחיה לתכנון")
        if len(cleaned) > 10000:
            raise ValueError("ההנחיה ארוכה מדי")
        return cleaned


class PackageInspect(PackageCreate):
    root_id: str

    @field_validator("root_id")
    @classmethod
    def inspection_id_required(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("נדרש מזהה בדיקה")
        if len(cleaned) > 256:
            raise ValueError("המזהה ארוך מדי")
        return cleaned


class AgentContentCreate(BaseModel):
    content_key: Optional[str] = None
    kind: Literal["skill", "prompt"]
    name: str
    description: str = ""
    content: str
    user_selectable: bool = False


class SkillPreviewSection(BaseModel):
    """One sample summary section fed to a Skill under test."""

    workflow_key: str = "sample"
    name: str
    status: str = "completed"
    summary: str = ""
    facts: List[str] = []
    warnings: List[str] = []


class SkillPreview(BaseModel):
    """Try unsaved Skill instructions against sample sections.

    An FDE could previously only judge a Skill by running a whole summary,
    which mixes package failures into what is really a wording question.
    This runs one Skill against supplied sections and persists nothing.
    """

    name: str = "טיוטת Skill"
    content: str
    question: str = ""
    sections: List[SkillPreviewSection]

    @field_validator("content")
    @classmethod
    def content_required(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("נדרשות הנחיות ל-Skill")
        if len(cleaned) > 20000:
            raise ValueError("ההנחיות ארוכות מדי")
        return cleaned

    @field_validator("sections")
    @classmethod
    def sections_required(cls, value):
        if not value:
            raise ValueError("נדרש לפחות חלק סיכום אחד לבדיקה")
        if len(value) > 10:
            raise ValueError("עד 10 חלקי סיכום בבדיקה")
        return value


class GeoBoundaries(BaseModel):
    """GeoJSON MultiPolygon scoping a summary request, drawn on the map.

    Mirrors LocatoAI's boundary contract and the frontend's
    ``GeoJSONMultiPolygon``. Coordinates are [lng, lat] (RFC 7946).
    """

    type: Literal["MultiPolygon"]
    coordinates: List[List[List[List[float]]]]

    @field_validator("coordinates")
    @classmethod
    def rings_are_closed(cls, value):
        if not value:
            raise ValueError("נדרש לפחות פוליגון אחד")
        for polygon in value:
            if not polygon:
                raise ValueError("פוליגון ללא טבעות")
            for ring in polygon:
                if len(ring) < 4:
                    raise ValueError("טבעת חייבת לכלול לפחות 4 נקודות")
                if any(len(point) < 2 for point in ring):
                    raise ValueError("נקודה חייבת לכלול קו אורך וקו רוחב")
                if ring[0][:2] != ring[-1][:2]:
                    raise ValueError("טבעת הפוליגון חייבת להיסגר")
        return value


class SummaryCreate(BaseModel):
    """A summary request scoped by an identifier, an area, or both.

    Either ``root_id`` or ``boundaries`` must be present. A request carrying
    only an area runs the published workflows whose steps read
    ``workflow.boundaries``; steps needing ``workflow.id`` degrade to a
    warning rather than failing the run.
    """

    root_id: Optional[str] = None
    question: str = ""
    skill_keys: List[str] = Field(default_factory=list)
    boundaries: Optional[GeoBoundaries] = None

    @field_validator("root_id")
    @classmethod
    def root_is_string(cls, value):
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            return None
        if len(cleaned) > 256:
            raise ValueError("המזהה ארוך מדי")
        return cleaned

    @field_validator("skill_keys")
    @classmethod
    def valid_skill_keys(cls, values: List[str]) -> List[str]:
        cleaned = list(dict.fromkeys(
            value.strip() for value in values if value.strip()
        ))
        if len(cleaned) > 3:
            raise ValueError("אפשר לבחור עד 3 Skills")
        return cleaned

    @model_validator(mode="after")
    def scope_required(self):
        if not self.root_id and not self.boundaries:
            raise ValueError("נדרש מזהה או אזור על המפה")
        return self


class DryRunCreate(BaseModel):
    """An FDE dry run always tests one concrete identifier.

    Separate from ``SummaryCreate``, which now accepts an area instead of an
    identifier; a dry run has no map to draw on.
    """

    root_id: str
    question: str = "בדיקת FDE"

    @field_validator("root_id")
    @classmethod
    def root_required(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("נדרש מזהה")
        if len(cleaned) > 256:
            raise ValueError("המזהה ארוך מדי")
        return cleaned


class FollowUpCreate(BaseModel):
    question: str
    skill_keys: List[str] = Field(default_factory=list)

    @field_validator("question")
    @classmethod
    def question_required(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("נדרשת שאלה")
        return cleaned

    @field_validator("skill_keys")
    @classmethod
    def valid_skill_keys(cls, values: List[str]) -> List[str]:
        return SummaryCreate.valid_skill_keys(values)


class FeedbackCreate(BaseModel):
    run_id: str
    rating: Literal[-1, 1]
    comment: str = ""


class ModelsProbeRequest(BaseModel):
    """Unsaved LLM connection settings used to probe available models.

    Empty, omitted, or masked means "use the saved value", so the panel can
    check a typed base URL without the user re-entering a stored API key.
    """

    llm_base_url: Optional[str] = None
    openai_api_key: Optional[str] = None

    def override(self, name: str) -> Optional[str]:
        value = (getattr(self, name) or "").strip()
        return None if not value or value == MASKED_SECRET else value
