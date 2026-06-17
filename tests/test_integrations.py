import pytest
from src.telegram_digest import generate_digest_message, send_telegram_digest
from src.sheets_export import export_to_sheets


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