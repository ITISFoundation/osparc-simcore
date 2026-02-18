# pylint:disable=contextmanager-generator-missing-cleanup
# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument


import asyncio
from datetime import timedelta

import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.postgres_tools import (
    PostgresTestConfig,
)
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_postgres_database.models.p_scheduler import ps_step_lease
from simcore_service_dynamic_scheduler.services.base_repository import (
    get_repository,
)
from simcore_service_dynamic_scheduler.services.p_scheduler._models import StepId, WorkerId
from simcore_service_dynamic_scheduler.services.p_scheduler._repositories import StepsLeaseRepository
from sqlalchemy.engine.row import Row
from sqlalchemy.ext.asyncio import AsyncEngine

pytest_simcore_core_services_selection = [
    "postgres",
]
pytest_simcore_ops_services_selection = [
    "adminer",
]


@pytest.fixture
def app_environment(
    app_environment: EnvVarsDict,
    disable_generic_scheduler_lifespan: None,
    postgres_db: sa.engine.Engine,
    postgres_host_config: PostgresTestConfig,
    disable_rabbitmq_lifespan: None,
    disable_redis_lifespan: None,
    disable_service_tracker_lifespan: None,
    disable_deferred_manager_lifespan: None,
    disable_notifier_lifespan: None,
    disable_status_monitor_lifespan: None,
    disable_p_scheduler_lifespan: None,
    monkeypatch: pytest.MonkeyPatch,
) -> EnvVarsDict:
    setenvs_from_dict(
        monkeypatch,
        {
            "POSTGRES_CLIENT_NAME": "test_postgres_client",
        },
    )
    return app_environment


@pytest.fixture
def engine(app: FastAPI) -> AsyncEngine:
    assert isinstance(app.state.engine, AsyncEngine)
    return app.state.engine


@pytest.fixture()
def steps_lease_repo(app: FastAPI) -> StepsLeaseRepository:
    return get_repository(app, StepsLeaseRepository)


@pytest.fixture
def worker_one() -> WorkerId:
    return "worker_one"


@pytest.fixture
def worker_two() -> WorkerId:
    return "worker_two"


@pytest.fixture
def lease_duration() -> timedelta:
    return timedelta(seconds=0.2)


async def _get_lease(engine: AsyncEngine, step_id: StepId) -> Row:
    async with engine.connect() as conn:
        result = await conn.execute(sa.select("*").where(ps_step_lease.c.step_id == step_id))
    row = result.first()
    assert row is not None
    return row


async def _assert_lease(
    engine: AsyncEngine, step_id: StepId, *, expected_owner: WorkerId, expected_renew_count
) -> None:
    lease = await _get_lease(engine, step_id)
    assert lease.owner == expected_owner
    assert lease.renew_count == expected_renew_count


async def test_acquire_or_extend_lease(
    steps_lease_repo: StepsLeaseRepository,
    step_id: StepId,
    worker_one: WorkerId,
    worker_two: WorkerId,
    lease_duration: timedelta,
) -> None:
    # Acquire a new lease
    acquired = await steps_lease_repo.acquire_or_extend_lease(step_id, worker_one, lease_duration=lease_duration)
    assert acquired is True
    await _assert_lease(steps_lease_repo.engine, step_id, expected_owner=worker_one, expected_renew_count=1)

    # Extend the existing lease
    acquired = await steps_lease_repo.acquire_or_extend_lease(step_id, worker_one, lease_duration=lease_duration)
    assert acquired is True
    await _assert_lease(steps_lease_repo.engine, step_id, expected_owner=worker_one, expected_renew_count=2)

    # Another worker should not be able to acquire the lease
    acquired = await steps_lease_repo.acquire_or_extend_lease(step_id, worker_two, lease_duration=lease_duration)
    assert acquired is False
    await _assert_lease(steps_lease_repo.engine, step_id, expected_owner=worker_one, expected_renew_count=2)

    await asyncio.sleep(lease_duration.total_seconds())

    # After lease expires another worker can acquire it
    acquired = await steps_lease_repo.acquire_or_extend_lease(step_id, worker_two, lease_duration=lease_duration)
    assert acquired is True
    await _assert_lease(steps_lease_repo.engine, step_id, expected_owner=worker_two, expected_renew_count=3)
