# pylint:disable=contextmanager-generator-missing-cleanup
# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

import asyncio
from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import Final

import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from pydantic import NonNegativeInt
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.postgres_tools import (
    PostgresTestConfig,
)
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_postgres_database.models.p_scheduler import ps_steps
from simcore_service_dynamic_scheduler.services.base_repository import (
    get_repository,
)
from simcore_service_dynamic_scheduler.services.p_scheduler import BaseStep
from simcore_service_dynamic_scheduler.services.p_scheduler._models import RunId, Step, StepId, StepState
from simcore_service_dynamic_scheduler.services.p_scheduler._repositories import StepsRepository
from simcore_service_dynamic_scheduler.services.p_scheduler._repositories.steps import _row_to_step
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
def steps_repo(app: FastAPI) -> StepsRepository:
    return get_repository(app, StepsRepository)


@pytest.fixture
def number_of_steps() -> NonNegativeInt:
    return 3


async def _get_step_row(engine: AsyncEngine, *, step_id: StepId | None = None, run_id: RunId | None = None) -> Row:
    assert step_id is not None or run_id is not None, "At least one of step_id or run_id must be provided"

    async with engine.connect() as conn:
        result = await conn.execute(
            sa.select("*").where(
                (ps_steps.c.step_id == step_id)
                if step_id is not None
                else sa.text("TRUE") & (ps_steps.c.run_id == run_id)
                if run_id is not None
                else sa.text("TRUE")
            )
        )
    row = result.first()
    assert row is not None
    return row


async def _assert_step_state(engine: AsyncEngine, run_id: RunId, expected_state: StepState) -> None:
    step_row = await _get_step_row(engine, run_id=run_id)
    assert StepState(step_row.state) == expected_state


_CANCELLABLE_STATES: Final[set[StepState]] = {StepState.CREATED, StepState.READY, StepState.RUNNING}


class _AStep(BaseStep):
    @classmethod
    def get_apply_timeout(cls) -> timedelta:
        return timedelta(seconds=42)

    @classmethod
    def get_revert_timeout(cls) -> timedelta:
        return timedelta(seconds=24)


async def test_create_step(steps_repo: StepsRepository, run_id: RunId):
    step = await steps_repo.create_step(run_id, _AStep.get_unique_reference(), step_class=_AStep, is_reverting=False)
    assert step.run_id == run_id

    step_row = await _get_step_row(steps_repo.engine, step_id=step.step_id)
    assert _row_to_step(step_row) == step


@pytest.mark.parametrize("cancellable_state", _CANCELLABLE_STATES)
async def test_set_run_steps_as_cancelled_with_cancellable_states(
    engine: AsyncEngine,
    steps_repo: StepsRepository,
    run_id: RunId,
    create_step_in_db: Callable[..., Awaitable[Step]],
    cancellable_state: StepState,
    number_of_steps: NonNegativeInt,
):
    steps = await asyncio.gather(*[create_step_in_db(state=cancellable_state) for _ in range(number_of_steps)])
    await _assert_step_state(engine, run_id, expected_state=cancellable_state)

    assert await steps_repo.set_run_steps_as_cancelled(run_id) == {step.step_id for step in steps}
    await _assert_step_state(engine, run_id, expected_state=StepState.CANCELLED)


@pytest.mark.parametrize("non_cancellable_state", set(StepState) - _CANCELLABLE_STATES)
async def test_set_run_steps_as_cancelled_with_non_cancellable_states(
    engine: AsyncEngine,
    steps_repo: StepsRepository,
    run_id: RunId,
    create_step_in_db: Callable[..., Awaitable[Step]],
    non_cancellable_state: StepState,
    number_of_steps: NonNegativeInt,
):
    await asyncio.gather(*[create_step_in_db(state=non_cancellable_state) for _ in range(number_of_steps)])
    await create_step_in_db(state=non_cancellable_state)
    await _assert_step_state(engine, run_id, expected_state=non_cancellable_state)

    assert await steps_repo.set_run_steps_as_cancelled(run_id) == set()
    await _assert_step_state(engine, run_id, expected_state=non_cancellable_state)


async def test_get_all_run_tracked_steps(
    steps_repo: StepsRepository,
    run_id: RunId,
    create_step_in_db: Callable[..., Awaitable[Step]],
    number_of_steps: NonNegativeInt,
):
    steps = await asyncio.gather(*[create_step_in_db() for _ in range(number_of_steps)])

    tracked_steps = await steps_repo.get_all_run_tracked_steps(run_id)
    assert tracked_steps == {(step.step_type, step.is_reverting) for step in steps}


async def test_get_all_run_tracked_steps_states(
    steps_repo: StepsRepository,
    run_id: RunId,
    create_step_in_db: Callable[..., Awaitable[Step]],
    number_of_steps: NonNegativeInt,
):
    steps = await asyncio.gather(*[create_step_in_db() for _ in range(number_of_steps)])

    tracked_steps_states = await steps_repo.get_all_run_tracked_steps_states(run_id)
    assert tracked_steps_states == {(step.step_type, step.is_reverting): step for step in steps}
