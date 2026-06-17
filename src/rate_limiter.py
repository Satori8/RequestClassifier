import asyncio
import time
import logging

logger = logging.getLogger(__name__)


class RateLimiter:
    def __init__(self, rpm_limit: int, tpm_limit: int):
        self.rpm_limit = rpm_limit
        self.tpm_limit = tpm_limit
        self.request_timestamps: list[float] = []
        self.token_records: list[tuple[float, int]] = []
        self.lock = asyncio.Lock()

    async def acquire(self, estimated_tokens: int = 1000):
        async with self.lock:
            while True:
                now = time.time()
                # Clean up records older than 60 seconds
                self.request_timestamps = [t for t in self.request_timestamps if now - t < 60]
                self.token_records = [r for r in self.token_records if now - r[0] < 60]

                current_requests = len(self.request_timestamps)
                current_tokens = sum(r[1] for r in self.token_records)

                # Check RPM
                if current_requests >= self.rpm_limit:
                    oldest_req_time = self.request_timestamps[0]
                    wait_time = 60.0 - (now - oldest_req_time) + 0.1
                    if wait_time > 0:
                        logger.warning(
                            f"RPM limit approached ({current_requests}/{self.rpm_limit} requests in last 60s). "
                            f"Pausing execution for {wait_time:.2f} seconds to respect API limits..."
                        )
                        await asyncio.sleep(wait_time)
                        continue

                # Check TPM
                if current_tokens + estimated_tokens >= self.tpm_limit:
                    oldest_token_time = self.token_records[0][0]
                    wait_time = 60.0 - (now - oldest_token_time) + 0.1
                    if wait_time > 0:
                        logger.warning(
                            f"TPM limit approached ({current_tokens}/{self.tpm_limit} tokens in last 60s). "
                            f"Pausing execution for {wait_time:.2f} seconds to respect API limits..."
                        )
                        await asyncio.sleep(wait_time)
                        continue

                # Slot acquired
                self.request_timestamps.append(now)
                self.token_records.append((now, estimated_tokens))
                break

    def record_actual(self, estimated_tokens: int, actual_tokens: int):
        if self.token_records:
            for i in range(len(self.token_records) - 1, -1, -1):
                if self.token_records[i][1] == estimated_tokens:
                    self.token_records[i] = (self.token_records[i][0], actual_tokens)
                    break
