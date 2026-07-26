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


class SummaryCreate(BaseModel):
    root_id: str
    question: str = ""

    @field_validator("root_id")
    @classmethod
    def root_is_string(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("נדרש מזהה")
        if len(cleaned) > 256:
            raise ValueError("המזהה ארוך מדי")
        return cleaned


class FollowUpCreate(BaseModel):
    question: str

    @field_validator("question")
    @classmethod
    def question_required(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("נדרשת שאלה")
        return cleaned


class AdminLogin(BaseModel):
    password: str


class FeedbackCreate(BaseModel):
    run_id: str
    rating: Literal[-1, 1]
    comment: str = ""
