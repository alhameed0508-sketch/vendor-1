"""
Retry utility for LLM provider calls.

Implements exponential backoff for transient failures (network timeouts,
rate limits, 5xx errors). Permanent failures (auth, invalid model) are
raised immediately.
"""

import logging
import time
from typing import Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Exceptions that should NOT be retried (permanent failures)
_PERMANENT_EXCEPTIONS = (
    ImportError,
    ValueError,
    TypeError,
    PermissionError,
)


def with_retry(
    fn: Callable[[], T],
    *,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    provider_name: str = "unknown",
) -> T:
    """Execute fn with exponential backoff on transient failures.

    Args:
        fn: Zero-argument callable to retry.
        max_attempts: Maximum number of attempts (default 3).
        base_delay: Initial delay in seconds (doubles each retry).
        provider_name: For logging context.

    Returns:
        The result of fn() on success.

    Raises:
        The last exception if all attempts fail, or immediately
        for permanent (non-retriable) errors.
    """
    last_exc = None

    for attempt in range(1, max_attempts + 1):
        try:
            return fn()
        except _PERMANENT_EXCEPTIONS:
            raise
        except Exception as exc:
            last_exc = exc
            if attempt == max_attempts:
                logger.error(
                    "[%s] LLM call failed after %d attempts: %s",
                    provider_name,
                    max_attempts,
                    exc,
                )
                raise

            delay = base_delay * (2 ** (attempt - 1))
            logger.warning(
                "[%s] LLM call failed (attempt %d/%d), retrying in %.1fs: %s",
                provider_name,
                attempt,
                max_attempts,
                delay,
                exc,
            )
            time.sleep(delay)

    raise last_exc  # unreachable but satisfies type checker
