from typing import Annotated, Type, Any
from pydantic import BaseModel, Field, create_model, AfterValidator


def get_classified_request_model(categories: list[str], departments: list[str]) -> Type[BaseModel]:
    """Dynamically create a Pydantic model for classified requests.

    Generates a schema with runtime validators that check category, department,
    priority, and complexity values against the loaded taxonomy lists. This
    dynamic approach avoids hardcoding taxonomy values as Pydantic Literal types,
    allowing the taxonomy to change without code changes.

    Each generated field uses Annotated types with AfterValidator to enforce
    taxonomy constraints at the Pydantic validation layer, providing immediate
    feedback on LLM output that doesn't match expected values.

    Args:
        categories: List of valid category ID strings from the taxonomy.
        departments: List of valid department ID strings from the taxonomy.

    Returns:
        A dynamically created Pydantic BaseModel subclass named "ClassifiedRequest"
        with validated fields for all classification attributes.
    """
    def check_category(v: str) -> str:
        """Validate that the category exists in the loaded taxonomy."""
        if v not in categories:
            raise ValueError(f"Category '{v}' is not in the allowed taxonomy: {categories}")
        return v

    def check_department(v: str | None) -> str | None:
        """Validate that the department exists in the loaded taxonomy, or allow None."""
        if v is not None and v not in departments:
            raise ValueError(f"Department '{v}' is not in the allowed taxonomy: {departments}")
        return v

    def check_priority(v: str) -> str:
        """Validate that the priority is one of the three allowed levels."""
        if v not in ["low", "medium", "high"]:
            raise ValueError(f"Priority '{v}' must be one of: low, medium, high")
        return v

    def check_complexity(v: str) -> str:
        """Validate that the complexity is one of the three allowed levels."""
        if v not in ["low", "medium", "high"]:
            raise ValueError(f"Complexity '{v}' must be one of: low, medium, high")
        return v

    CategoryType = Annotated[str, AfterValidator(check_category)]
    DepartmentType = Annotated[str | None, AfterValidator(check_department)]
    PriorityType = Annotated[str, AfterValidator(check_priority)]
    ComplexityType = Annotated[str, AfterValidator(check_complexity)]

    # Build the dynamic model with validated fields
    # Each field uses Annotated types to enforce taxonomy constraints at runtime
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
    """Wraps the outcome of processing a single request.

    Every input request produces exactly one ProcessingResult to guarantee
    no silent drops. Successful results carry the validated ClassifiedRequest
    object; failed results capture the error details and raw LLM output for
    debugging.

    Attributes:
        request: The validated ClassifiedRequest object, or None on error.
        processing_error: True if processing failed after all retries.
        error_message: Human-readable error description on failure.
        raw_llm_response: Raw LLM output text captured on validation failure.
        retries: Number of retry attempts made before success or failure.
        input_tokens: Token count of the prompt sent to the LLM.
        output_tokens: Token count of the LLM response.
    """
    request: Any | None = None
    processing_error: bool = False
    error_message: str | None = None
    raw_llm_response: str | None = None
    retries: int = 0
    input_tokens: int | None = None
    output_tokens: int | None = None
