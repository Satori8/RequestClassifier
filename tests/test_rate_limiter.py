import asyncio
import time
import pytest
from src.rate_limiter import RateLimiter


@pytest.mark.asyncio
async def test_rate_limiter_rpm():
    limiter = RateLimiter(rpm_limit=2, tpm_limit=10000)

    start_time = time.time()
    await limiter.acquire(100)
    await limiter.acquire(100)

    # Third acquire should trigger wait since RPM limit is 2
    task = asyncio.create_task(limiter.acquire(100))
    await asyncio.sleep(0.1)
    assert not task.done()

    # Clean up task
    task.cancel()
