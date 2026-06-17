import os
import logging
import gspread
from typing import Any
from src.schemas import ProcessingResult

logger = logging.getLogger(__name__)

def export_to_sheets(results: list[ProcessingResult], credentials_path: str | None, spreadsheet_id: str | None) -> bool:
    if not credentials_path or not spreadsheet_id:
        logger.warning("Google Sheets credentials path or spreadsheet ID is missing. Skipping export.")
        return False

    if not os.path.exists(credentials_path):
        logger.warning(f"Google Sheets credentials file not found at {credentials_path}. Skipping export.")
        return False

    try:
        gc = gspread.service_account(filename=credentials_path)
        sh = gc.open_by_key(spreadsheet_id)
        worksheet = sh.get_worksheet(0)
        if not worksheet:
            worksheet = sh.get_worksheet(0)

        # Prepare headers and rows
        headers = [
            "id", "channel", "timestamp", "category", "target_department", 
            "priority", "short_summary", "requested_actions", "needs_clarification", 
            "confidence_score", "estimated_complexity", "language"
        ]
        
        # Check if sheet is empty to write headers
        existing_values = worksheet.get_all_values()
        if not existing_values:
            worksheet.append_row(headers)

        rows = []
        for r in results:
            if not r.processing_error and r.request:
                req = r.request
                rows.append([
                    req.id,
                    req.channel,
                    req.timestamp,
                    req.category,
                    req.target_department or "",
                    req.priority,
                    req.short_summary,
                    ", ".join(req.requested_actions),
                    str(req.needs_clarification),
                    req.confidence_score,
                    req.estimated_complexity,
                    req.language
                ])
                
        if rows:
            worksheet.append_rows(rows)
            logger.info(f"Successfully exported {len(rows)} rows to Google Sheets.")
            return True
        return False
    except Exception as e:
        logger.error(f"Failed to export to Google Sheets: {e}")
        return False