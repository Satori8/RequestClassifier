import pytest
from unittest.mock import MagicMock, patch
from src.telegram_digest import generate_digest_message, send_telegram_digest
from src.sheets_export import export_to_sheets
from src.schemas import ProcessingResult


def test_generate_digest_message():
    analytics = {
        "summary": {
            "total_requests": 10,
            "successfully_processed": 9,
            "failed_processing": 1,
            "average_confidence_score": 0.95
        },
        "by_category": {"автоматизація": 5, "інтеграція": 4},
        "by_department": {"маркетинг": 3},
        "by_priority": {"high": 2, "medium": 7}
    }
    
    msg = generate_digest_message(analytics)
    assert "<b>Всього оброблено:</b> 10" in msg
    assert "<b>Успішно:</b> 9" in msg
    assert "<b>Помилки:</b> 1" in msg
    assert "автоматизація: 5" in msg
    assert "high: 2" in msg


@pytest.mark.asyncio
async def test_send_telegram_missing_config():
    # Should skip gracefully and return False
    res = await send_telegram_digest({}, None, None)
    assert not res


def test_export_sheets_missing_config():
    # Should skip gracefully and return False
    res = export_to_sheets([], None, None)
    assert not res


@patch("src.sheets_export.gspread.service_account")
@patch("src.sheets_export.os.path.exists")
def test_export_to_sheets_success(mock_exists, mock_service_account):
    from pydantic import BaseModel
    
    class DummyRequest(BaseModel):
        id: str
        channel: str
        timestamp: str
        raw_text: str
        category: str
        target_department: str | None
        priority: str
        short_summary: str
        requested_actions: list[str]
        needs_clarification: bool
        confidence_score: float
        estimated_complexity: str
        language: str

    req = DummyRequest(
        id="REQ-001",
        channel="Slack",
        timestamp="2026-06-08 09:14",
        raw_text="Test raw text",
        category="автоматизація",
        target_department="маркетинг",
        priority="high",
        short_summary="Test summary",
        requested_actions=["Action 1"],
        needs_clarification=False,
        confidence_score=0.9,
        estimated_complexity="low",
        language="uk"
    )

    results = [ProcessingResult(request=req)]

    mock_exists.return_value = True
    mock_gc = MagicMock()
    mock_sh = MagicMock()
    mock_ws = MagicMock()
    
    mock_service_account.return_value = mock_gc
    mock_gc.open_by_key.return_value = mock_sh
    mock_sh.get_worksheet.return_value = mock_ws
    mock_ws.get_all_values.return_value = [] # Empty sheet

    res = export_to_sheets(results, "dummy_creds.json", "dummy_sheet_id")
    
    assert res
    mock_ws.append_row.assert_called_once() # Headers
    mock_ws.append_rows.assert_called_once() # Rows
    
    # Check that raw_text is in the rows
    called_rows = mock_ws.append_rows.call_args[0][0]
    assert called_rows[0][3] == "Test raw text"