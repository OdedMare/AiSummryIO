from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


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
    root_id: str
    question: str = ""
    skill_keys: List[str] = Field(default_factory=list)
    boundaries: Optional[GeoBoundaries] = None

    @field_validator("root_id")
    @classmethod
    def root_is_string(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("נדרש מזהה")
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


class AdminLogin(BaseModel):
    password: str


class FeedbackCreate(BaseModel):
    run_id: str
    rating: Literal[-1, 1]
    comment: str = ""
