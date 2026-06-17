from typing import Annotated, Type, Any
from pydantic import BaseModel, Field, create_model, AfterValidator


def get_classified_request_model(categories: list[str], departments: list[str]) -> Type[BaseModel]:
    def check_category(v: str) -> str:
        if v not in categories:
            raise ValueError(f"Category '{v}' is not in the allowed taxonomy: {categories}")
        return v

    def check_department(v: str | None) -> str | None:
        if v is not None and v not in departments:
            raise ValueError(f"Department '{v}' is not in the allowed taxonomy: {departments}")
        return v

    def check_priority(v: str) -> str:
        if v not in ["low", "medium", "high"]:
            raise ValueError(f"Priority '{v}' must be one of: low, medium, high")
        return v

    def check_complexity(v: str) -> str:
        if v not in ["low", "medium", "high"]:
            raise ValueError(f"Complexity '{v}' must be one of: low, medium, high")
        return v

    CategoryType = Annotated[str, AfterValidator(check_category)]
    DepartmentType = Annotated[str | None, AfterValidator(check_department)]
    PriorityType = Annotated[str, AfterValidator(check_priority)]
    ComplexityType = Annotated[str, AfterValidator(check_complexity)]

    return create_model(
        "ClassifiedRequest",
        id=(str, Field(description="The unique request ID (e.g., REQ-001)")),
        channel=(str, Field(description="The source channel (e.g., Slack, Telegram, Email)")),
        timestamp=(str, Field(description="The ISO timestamp of the request")),
        raw_text=(str, Field(description="The raw text of the request")),
        category=(CategoryType, Field(description="The classified category from the taxonomy")),
        target_department=(DepartmentType, Field(description="The target department or null if unclear")),
        priority=(PriorityType, Field(description="The priority level based on rules")),
        short_summary=(str, Field(description="One-sentence summary in Ukrainian")),
        requested_actions=(list[str], Field(description="Concrete action items, can be empty")),
        needs_clarification=(bool, Field(description="True if the request is vague, missing context, or out-of-scope")),
        confidence_score=(float, Field(description="LLM self-assessed confidence score between 0.0 and 1.0", ge=0.0, le=1.0)),
        clarification_questions=(list[str], Field(description="1-3 questions if needs_clarification is True, else empty list")),
        estimated_complexity=(ComplexityType, Field(description="Estimated task complexity")),
        language=(str, Field(description="Detected language: 'uk' or 'en'")),
        __base__=BaseModel
    )


class ProcessingResult(BaseModel):
    request: Any | None = None
    processing_error: bool = False
    error_message: str | None = None
    raw_llm_response: str | None = None
    retries: int = 0
    input_tokens: int | None = None
    output_tokens: int | None = None
