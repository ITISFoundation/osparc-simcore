import logging
from typing import cast
from unittest.mock import Mock

import pytest
from simcore_service_director_v2.api.dependencies.database import get_base_repository
from simcore_service_director_v2.modules.db.repositories import BaseRepository
from sqlalchemy.ext.asyncio import AsyncEngine


class DummyRepository(BaseRepository):
    pass


def _create_mocked_engine(*, checked_out: int, pool_size: int, max_overflow: int) -> AsyncEngine:
    mocked_pool = Mock(_max_overflow=max_overflow)
    mocked_pool.checkedout.return_value = checked_out
    mocked_pool.size.return_value = pool_size
    mocked_pool.status.return_value = (
        f"Pool size: {pool_size} Current Overflow: {checked_out - pool_size} "
        f"Current Checked out connections: {checked_out}"
    )

    mocked_engine = cast(AsyncEngine, Mock(spec=AsyncEngine))
    mocked_engine.pool = mocked_pool
    return mocked_engine


def test_get_base_repository_does_not_warn_on_transient_spikes_with_available_overflow(
    caplog: pytest.LogCaptureFixture,
):
    engine = _create_mocked_engine(checked_out=10, pool_size=10, max_overflow=20)

    with caplog.at_level(logging.WARNING, logger="simcore_service_director_v2.api.dependencies.database"):
        repository = get_base_repository(engine=engine, repo_type=DummyRepository)

    assert isinstance(repository, DummyRepository)
    assert "Database connection pool near limits" not in caplog.text


def test_get_base_repository_warns_when_nearing_total_capacity(
    caplog: pytest.LogCaptureFixture,
):
    engine = _create_mocked_engine(checked_out=27, pool_size=10, max_overflow=20)

    with caplog.at_level(logging.WARNING, logger="simcore_service_director_v2.api.dependencies.database"):
        repository = get_base_repository(engine=engine, repo_type=DummyRepository)

    assert isinstance(repository, DummyRepository)
    assert "Database connection pool near limits" in caplog.text
    assert "checked_out=27" in caplog.text
    assert "threshold=27" in caplog.text
    assert "total_capacity=30" in caplog.text
    assert "utilization=90.0%" in caplog.text
