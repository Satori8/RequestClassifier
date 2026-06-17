import logging
import httpx
from typing import Any

logger = logging.getLogger(__name__)

def generate_digest_message(analytics: dict[str, Any]) -> str:
    summary = analytics.get("summary", {})
    by_category = analytics.get("by_category", {})
    by_priority = analytics.get("by_priority", {})

    categories_lines = "\n".join([f"• {k}: {v}" for k, v in by_category.items()])
    priorities_lines = "\n".join([f"• {k}: {v}" for k, v in by_priority.items()])

    return f"""<b>📊 Щоденний звіт класифікації запитів</b>

✅ <b>Всього оброблено:</b> {summary.get('total_requests', 0)}
✔️ <b>Успішно:</b> {summary.get('successfully_processed', 0)}
❌ <b>Помилки:</b> {summary.get('failed_processing', 0)}
🎯 <b>Сер. впевненість:</b> {summary.get('average_confidence_score', 0.0) * 100:.1f}%

🗂 <b>Категорії:</b>
{categories_lines or "• Немає"}

⚠️ <b>Пріоритети:</b>
{priorities_lines or "• Немає"}
"""

async def send_telegram_digest(analytics: dict[str, Any], bot_token: str | None, chat_id: str | None) -> bool:
    if not bot_token or not chat_id:
        logger.warning("Telegram Bot Token or Chat ID is missing. Skipping digest send.")
        return False

    message = generate_digest_message(analytics)
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML"
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, timeout=10.0)
            if response.status_code == 200:
                logger.info("Successfully sent Telegram digest.")
                return True
            else:
                logger.error(f"Failed to send Telegram digest: {response.text}")
                return False
    except Exception as e:
        logger.error(f"Error sending Telegram digest: {e}")
        return False