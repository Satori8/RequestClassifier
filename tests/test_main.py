import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.main import process_single_request
from src.progress import ProgressTracker
from src.rate_limiter import RateLimiter
from src.schemas import ProcessingResult


@pytest.mark.asyncio
async def test_process_single_request_success():
    req = {"id": "REQ-001", "channel": "Slack", "timestamp": "2026-06-08 09:14", "raw_text": "Test"}
    client = MagicMock()
    settings = MagicMock()
    settings.MODEL_NAME = "gemini-3.5-flash"
    settings.TEMPERATURE = 0.0
    settings.MAX_OUTPUT_TOKENS = 1024
    
    response_schema = MagicMock()
    taxonomy = {}
    rate_limiter = AsyncMock(spec=RateLimiter)
    
    progress_tracker = MagicMock(spec=ProgressTracker)
    semaphore = asyncio.Semaphore(1)
    
    dummy_result = ProcessingResult(request=MagicMock(), processing_error=False)
    
    with patch("src.main.classify_request", new_callable=AsyncMock) as mock_classify:
        mock_classify.return_value = dummy_result
        
        res = await process_single_request(
            req, client, settings, response_schema, taxonomy, rate_limiter, progress_tracker, semaphore, "batch"
        )
        
        assert not res.processing_error
        progress_tracker.mark_completed.assert_called_once_with("REQ-001")


@pytest.mark.asyncio
@patch("src.main.read_input_requests")
@patch("src.main.ProgressTracker")
@patch("src.main.generate_reports")
@patch("src.main.export_to_sheets")
@patch("src.main.send_telegram_digest")
@patch("src.main.genai.Client")
@patch("src.main.shutil.move")
@patch("src.main.os.path.exists")
async def test_async_main_moves_file(
    mock_exists, mock_move, mock_client, mock_telegram, mock_sheets, mock_reports, mock_tracker_cls, mock_read_requests
):
    from src.main import async_main
    
    # Mock requests and settings
    mock_read_requests.return_value = [{"id": "REQ-001", "raw_text": "Test"}]
    mock_tracker = MagicMock()
    mock_tracker.is_processed.return_value = True
    mock_tracker_cls.return_value = mock_tracker
    
    mock_exists.return_value = True
    
    with patch("src.main.Settings") as mock_settings_cls:
        mock_settings = MagicMock()
        mock_settings.INPUT_CSV_PATH = "dummy.csv"
        mock_settings.SEMAPHORE_LIMIT = 5
        mock_settings.RPM_LIMIT = 15
        mock_settings.TPM_LIMIT = 1000000
        mock_settings_cls.return_value = mock_settings
        
        await async_main()
        
        mock_move.assert_called_once()

