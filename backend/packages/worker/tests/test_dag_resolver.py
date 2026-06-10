"""Tests for dag_resolver — cycle detection (unit tests using mocked DB)."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

from shared.models.job_dependency import JobDependency
from worker.scheduler.dag_resolver import validate_no_cycles


def _make_edge(parent: uuid.UUID, child: uuid.UUID) -> JobDependency:
    dep = MagicMock(spec=JobDependency)
    dep.parent_job_id = parent
    dep.child_job_id = child
    return dep


def _mock_session(edges: list[JobDependency]) -> AsyncMock:
    """Create a mock AsyncSession that returns *edges* when executed."""
    session = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = edges
    session.execute.return_value = result
    return session


class TestValidateNoCycles:
    async def test_no_parents_is_always_valid(self) -> None:
        session = _mock_session([])
        new_job = uuid.uuid4()
        valid = await validate_no_cycles(new_job, [], session)
        assert valid is True

    async def test_simple_chain_is_valid(self) -> None:
        """A → B → new_job (no cycle)."""
        a, b, new_job = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        edges = [_make_edge(a, b)]
        session = _mock_session(edges)
        valid = await validate_no_cycles(new_job, [b], session)
        assert valid is True

    async def test_direct_self_loop_detected(self) -> None:
        """new_job depends on itself → cycle."""
        new_job = uuid.uuid4()
        session = _mock_session([])
        # parent_ids includes new_job itself — DFS from new_job reaches new_job immediately
        valid = await validate_no_cycles(new_job, [new_job], session)
        assert valid is False

    async def test_indirect_cycle_detected(self) -> None:
        """A → new_job exists; adding new_job → A creates cycle A ↔ new_job."""
        a, new_job = uuid.uuid4(), uuid.uuid4()
        # Existing edge: a depends on new_job
        edges = [_make_edge(new_job, a)]
        session = _mock_session(edges)
        # We're adding new_job depends on a → a's ancestor chain includes new_job
        valid = await validate_no_cycles(new_job, [a], session)
        assert valid is False

    async def test_long_chain_no_cycle(self) -> None:
        """A → B → C → D, adding D → new_job should be valid."""
        a, b, c, d, new_job = [uuid.uuid4() for _ in range(5)]
        edges = [_make_edge(a, b), _make_edge(b, c), _make_edge(c, d)]
        session = _mock_session(edges)
        valid = await validate_no_cycles(new_job, [d], session)
        assert valid is True

    async def test_diamond_dependency_valid(self) -> None:
        """
        A → B → D
        A → C → D
        (Diamond shape, no cycle)
        """
        a, b, c, d, new_job = [uuid.uuid4() for _ in range(5)]
        edges = [
            _make_edge(a, b),
            _make_edge(a, c),
            _make_edge(b, d),
            _make_edge(c, d),
        ]
        session = _mock_session(edges)
        valid = await validate_no_cycles(new_job, [d], session)
        assert valid is True

    async def test_multiple_parents_no_cycle(self) -> None:
        """new_job depends on A and B (both independent leaves)."""
        a, b, new_job = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        session = _mock_session([])
        valid = await validate_no_cycles(new_job, [a, b], session)
        assert valid is True
