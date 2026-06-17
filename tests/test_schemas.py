from pydantic import ValidationError
import pytest
from src.schemas import get_classified_request_model


def test_dynamic_model_validation_success():
    categories = ["автоматизація", "інтеграція"]
    departments = ["маркетинг", "продажі"]

    Model = get_classified_request_model(categories, departments)

    valid_data = {
        "id": "REQ-001",
        "channel": "Slack",
        "timestamp": "2026-06-08 09:14",
        "raw_text": "Test",
        "category": "автоматизація",
        "target_department": "маркетинг",
        "priority": "low",
        "short_summary": "Test summary",
        "requested_actions": ["Action 1"],
        "needs_clarification": False,
        "confidence_score": 0.95,
        "clarification_questions": [],
        "estimated_complexity": "low",
        "language": "uk",
    }

    instance = Model.model_validate(valid_data)
    assert instance.category == "автоматизація"
    assert instance.target_department == "маркетинг"


def test_dynamic_model_validation_failure():
    categories = ["автоматизація"]
    departments = ["маркетинг"]
    Model = get_classified_request_model(categories, departments)

    invalid_data = {
        "id": "REQ-001",
        "channel": "Slack",
        "timestamp": "2026-06-08 09:14",
        "raw_text": "Test",
        "category": "неправильна_категорія",  # Invalid
        "target_department": "маркетинг",
        "priority": "low",
        "short_summary": "Test summary",
        "requested_actions": [],
        "needs_clarification": False,
        "confidence_score": 0.95,
        "clarification_questions": [],
        "estimated_complexity": "low",
        "language": "uk",
    }

    with pytest.raises(ValidationError):
        Model.model_validate(invalid_data)
