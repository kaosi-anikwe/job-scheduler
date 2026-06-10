"""Abstract base handler interface for job execution."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseHandler(ABC):
    """Base class for all job handlers.

    Each handler implements real business logic — not just returning 200.
    """

    @abstractmethod
    async def execute(self, job_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Execute the job and return a result dict.

        Parameters
        ----------
        job_id:
            The UUID of the job being executed.
        payload:
            The job's payload data.

        Returns
        -------
        dict:
            Result data to store in the execution log.

        Raises
        ------
        Exception:
            On failure — triggers retry logic.
        """
        ...
