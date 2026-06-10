"""Dead-letter queue management and threshold alerting.

Jobs that exhaust all retries are moved to the DLQ (status='failed',
retry_count >= max_retries). When the DLQ count exceeds a configurable
threshold, an email alert is sent.

Default threshold: 10 jobs (configurable via DLQ_ALERT_THRESHOLD env var).
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.config import get_settings
from shared.logging import get_logger
from shared.models.job import JobORM

logger = get_logger(__name__)


async def move_to_dlq(
    job: JobORM,
    error: Exception,
    session: AsyncSession,
) -> None:
    """Mark a job as failed and store error details for DLQ inspection.

    This does NOT commit — the caller manages the transaction.
    """
    job.status = "failed"
    job.error_details = {
        "error": str(error),
        "error_type": type(error).__name__,
        "final_retry_count": job.retry_count,
    }

    logger.warning(
        f"Job {job.id} moved to DLQ after {job.retry_count} retries",
        extra={"event": "MOVED_TO_DLQ", "job_id": str(job.id)},
    )


async def get_dlq_count(session: AsyncSession) -> int:
    """Return the number of jobs currently in the DLQ."""
    result = await session.execute(
        select(func.count(JobORM.id)).where(
            JobORM.status == "failed",
            JobORM.retry_count >= JobORM.max_retries,
        )
    )
    return result.scalar_one()


async def check_dlq_threshold(session: AsyncSession) -> bool:
    """Check if the DLQ count exceeds the alert threshold.

    Returns True if an alert should be sent.
    """
    settings = get_settings()
    count = await get_dlq_count(session)
    return count >= settings.DLQ_ALERT_THRESHOLD


async def send_dlq_alert(dlq_count: int) -> None:
    """Send a DLQ threshold alert email via SMTP.

    Uses ``aiosmtplib`` for async delivery. Falls back to logging if
    SMTP is unavailable.
    """
    settings = get_settings()

    subject = f"[ALERT] DLQ threshold exceeded: {dlq_count} failed jobs"
    body = (
        f"The dead-letter queue has reached {dlq_count} jobs, "
        f"exceeding the threshold of {settings.DLQ_ALERT_THRESHOLD}.\n\n"
        f"Please inspect the failed jobs and resolve the underlying issues.\n"
        f"API endpoint: GET /api/v1/dlq\n"
    )

    try:
        import aiosmtplib
        from email.mime.text import MIMEText

        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = "scheduler@dilamme.com"
        msg["To"] = settings.DLQ_ALERT_EMAIL

        await aiosmtplib.send(
            msg,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USER or None,
            password=settings.SMTP_PASSWORD or None,
        )

        logger.info(
            f"DLQ alert sent to {settings.DLQ_ALERT_EMAIL}",
            extra={"event": "DLQ_ALERT_SENT", "dlq_count": dlq_count},
        )
    except Exception:
        # SMTP failure should not crash the worker — log and continue
        logger.error(
            f"Failed to send DLQ alert email (count={dlq_count})",
            extra={"event": "DLQ_ALERT_FAILED", "dlq_count": dlq_count},
            exc_info=True,
        )
