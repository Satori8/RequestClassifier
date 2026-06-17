import os
import json
import pytest
from pydantic import BaseModel
from src.schemas import ProcessingResult
from src.report_generator import generate_reports


class DummyRequest(BaseModel):
    id: str
    category: str
    target_department: str | None
    priority: str
    confidence_score: float


def test_generate_reports(tmp_path):
    req1 = DummyRequest(id="REQ-001", category="автоматизація", target_department="маркетинг", priority="high", confidence_score=0.9)
    req2 = DummyRequest(id="REQ-002", category="інтеграція", target_department=None, priority="low", confidence_score=0.8)

    results = [
        ProcessingResult(request=req1),
        ProcessingResult(request=req2),
        ProcessingResult(processing_error=True, error_message="LLM Error")
    ]

    output_dir = tmp_path / "output"
    analytics = generate_reports(results, str(output_dir))

    assert analytics["summary"]["total_requests"] == 3
    assert analytics["summary"]["successfully_processed"] == 2
    assert analytics["summary"]["failed_processing"] == 1
    assert analytics["by_category"]["автоматизація"] == 1
    assert analytics["by_department"]["маркетинг"] == 1
    assert analytics["by_priority"]["high"] == 1

    assert os.path.exists(output_dir / "output.json")
    assert os.path.exists(output_dir / "analytics.json")