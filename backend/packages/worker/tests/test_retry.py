"""Tests for retry logic — backoff calculation and should_retry predicate."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

import pytest

from shared.models.job import Job
from worker.recovery.retry import calculate_backoff, should_retry


def make_job(retry_count: int = 0, max_retries: int = 3) -> Job:
    job = Job(
        type="send_email",
        scheduled_at=datetime.now(UTC),
        payload={},
    )
    job.retry_count = retry_count
    job.max_retries = max_retries
    return job


class TestCalculateBackoff:
    def test_attempt_1_base_delay_is_one(self) -> None:
        """5^(1-1) = 5^0 = 1.0, plus up to 1.5 jitter."""
        with patch("worker.recovery.retry.random.uniform", return_value=0.0):
            delay = calculate_backoff(1)
        assert delay == pytest.approx(1.0)

    def test_attempt_2_base_delay_is_five(self) -> None:
        """5^(2-1) = 5.0"""
        with patch("worker.recovery.retry.random.uniform", return_value=0.0):
            delay = calculate_backoff(2)
        assert delay == pytest.approx(5.0)

    def test_attempt_3_base_delay_is_25(self) -> None:
        """5^(3-1) = 25.0"""
        with patch("worker.recovery.retry.random.uniform", return_value=0.0):
            delay = calculate_backoff(3)
        assert delay == pytest.approx(25.0)

    def test_jitter_added(self) -> None:
        """Jitter of 1.5 should be added to the base delay."""
        with patch("worker.recovery.retry.random.uniform", return_value=1.5):
            delay = calculate_backoff(1)
        assert delay == pytest.approx(2.5)

    def test_delay_always_positive(self) -> None:
        for attempt in range(1, 6):
            delay = calculate_backoff(attempt)
            assert delay >= 0

    def test_exponential_growth(self) -> None:
        """Each subsequent attempt should have a strictly larger base delay."""
        with patch("worker.recovery.retry.random.uniform", return_value=0.0):
            delays = [calculate_backoff(i) for i in range(1, 5)]
        for i in range(len(delays) - 1):
            assert delays[i + 1] > delays[i]


class TestShouldRetry:
    def test_retry_when_count_below_max(self) -> None:
        job = make_job(retry_count=0, max_retries=3)
        assert should_retry(job) is True

    def test_retry_when_count_equals_max_minus_one(self) -> None:
        job = make_job(retry_count=2, max_retries=3)
        assert should_retry(job) is True

    def test_no_retry_when_count_equals_max(self) -> None:
        job = make_job(retry_count=3, max_retries=3)
        assert should_retry(job) is False

    def test_no_retry_when_count_exceeds_max(self) -> None:
        job = make_job(retry_count=5, max_retries=3)
        assert should_retry(job) is False

    def test_no_retry_when_max_retries_zero(self) -> None:
        job = make_job(retry_count=0, max_retries=0)
        assert should_retry(job) is False

    def test_retry_with_custom_max(self) -> None:
        job = make_job(retry_count=4, max_retries=5)
        assert should_retry(job) is True
