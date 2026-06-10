"""Handler registry — maps job type strings to handler classes."""

from __future__ import annotations

from worker.handlers.base import BaseHandler
from worker.handlers.email_handler import EmailHandler
from worker.handlers.log_handler import LogHandler
from worker.handlers.webhook_handler import WebhookHandler

# Maps job type → handler instance (singletons)
_REGISTRY: dict[str, BaseHandler] = {
    "send_email": EmailHandler(),
    "webhook": WebhookHandler(),
    "log_processing": LogHandler(),
}


def get_handler(job_type: str) -> BaseHandler | None:
    """Return the handler for the given job type, or None if not registered."""
    return _REGISTRY.get(job_type)


def register_handler(job_type: str, handler: BaseHandler) -> None:
    """Register a new handler for a job type (useful for testing)."""
    _REGISTRY[job_type] = handler


def list_handlers() -> list[str]:
    """Return all registered job type names."""
    return list(_REGISTRY.keys())
