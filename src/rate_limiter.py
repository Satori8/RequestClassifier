import asyncio
import time
import logging

logger = logging.getLogger(__name__)


class RateLimiter:
    """Sliding-window rate limiter for API calls (requests-per-minute and tokens-per-minute).

    Tracks request timestamps and token counts over a 60-second rolling window.
    When a limit is approached, the coroutine is paused until enough time has
    passed for old records to expire out of the window. Thread-safe via asyncio.Lock.

    This implements a precise sliding window (not a fixed bucket): records older
    than 60 seconds are pruned on each check, and wait time is calculated as the
    time until the oldest record expires.

    Args:
        rpm_limit: Maximum number of API requests allowed per 60-second window.
        tpm_limit: Maximum total tokens (input + output) allowed per 60-second window.
    """
    def __init__(self, rpm_limit: int, tpm_limit: int):
        self.rpm_limit = rpm_limit
        self.tpm_limit = tpm_limit
        # List of UNIX timestamps for each request made within the window
        self.request_timestamps: list[float] = []
        # List of (timestamp, token_count) tuples tracking token usage
        self.token_records: list[tuple[float, int]] = []
        self.lock = asyncio.Lock()

    async def acquire(self, estimated_tokens: int = 1000):
        """Block until a rate-limited slot is available, then record usage.

        Implements a busy-wait loop protected by an asyncio lock:
        1. Prune records older than 60 seconds from the sliding window.
        2. Check if RPM or TPM would be exceeded by adding this request.
        3. If exceeded, sleep until the oldest record falls out of the window.
        4. Repeat until a slot is acquired, then record the request.

        Args:
            estimated_tokens: Estimated token consumption for this request.
                Defaults to 1000 as a conservative estimate.
        """
        async with self.lock:
            while True:
                now = time.time()

                # --- Sliding window maintenance ---
                # Prune request timestamps older than the 60-second window.
                # This keeps the list bounded and ensures wait calculations
                # are based only on active records.
                self.request_timestamps = [t for t in self.request_timestamps if now - t < 60]
                # Same pruning for token records (tuple[timestamp, token_count])
                self.token_records = [r for r in self.token_records if now - r[0] < 60]

                current_requests = len(self.request_timestamps)
                current_tokens = sum(r[1] for r in self.token_records)

                # --- RPM check ---
                # If we've hit the request-per-minute cap, calculate how long
                # until the oldest request falls out of the 60-second window.
                # Adding 0.1s margin prevents tight re-check loops.
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

                # --- TPM check ---
                # If adding estimated_tokens would exceed the per-minute cap,
                # wait until the oldest token record ages out, freeing capacity.
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

                # --- Slot acquired ---
                # Record the current request's timestamp and estimated tokens
                # so they count toward the sliding window limits.
                self.request_timestamps.append(now)
                self.token_records.append((now, estimated_tokens))
                break

    def record_actual(self, estimated_tokens: int, actual_tokens: int):
        """Replace an estimated token count with the actual usage.

        After the API call completes, this corrects the earlier estimate
        with the real token count (input + output) for accurate TPM tracking.
        Scans backwards through token_records to find the matching estimate.

        Args:
            estimated_tokens: The estimate that was used when acquiring the slot.
            actual_tokens: The real token count returned by the API response.
        """
        if self.token_records:
            # Scan backwards to find the entry with matching estimated tokens.
            # Using reverse iteration to find the most recent match, which is
            # likely the one just added by the corresponding acquire() call.
            for i in range(len(self.token_records) - 1, -1, -1):
                if self.token_records[i][1] == estimated_tokens:
                    self.token_records[i] = (self.token_records[i][0], actual_tokens)
                    break
