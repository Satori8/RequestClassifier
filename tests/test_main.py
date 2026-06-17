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
