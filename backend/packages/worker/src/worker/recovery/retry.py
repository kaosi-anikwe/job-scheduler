"""Retry logic with exponential backoff and jitter.

Implements the formula from system design §7.1:
    T_wait = 5^(attempt - 1) + Uniform(0, 1.5)

This produces:
    Attempt 1 → ~1s
    Attempt 2 → ~5s
    Attempt 3 → ~25s
"""

from __future__ import annotations

import random

from shared.models.job import Job


def calculate_backoff(retry_count: int) -> float:
    """Calculate the backoff delay in seconds for a given retry attempt.

    Uses exponential backoff with jitter per system design §7.1.
    """
    base_delay = 5.0 ** (retry_count - 1)
    jitter = random.uniform(0.0, 1.5)
    return base_delay + jitter


def should_retry(job: Job) -> bool:
    """Return True if the job has remaining retry attempts."""
    return job.retry_count < job.max_retries
