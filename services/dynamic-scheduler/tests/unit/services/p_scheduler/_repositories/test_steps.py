# pylint:disable=contextmanager-generator-missing-cleanup
# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

import asyncio
from collections.abc import Awaitable, Callable
from copy import deepcopy
from datetime import datetime, timedelta
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
from simcore_postgres_database.models.p_scheduler import ps_step_fail_history, ps_steps
from simcore_service_dynamic_scheduler.services.base_repository import (
    get_repository,
)
from simcore_service_dynamic_scheduler.services.p_scheduler import BaseStep
from simcore_service_dynamic_scheduler.services.p_scheduler._abc import _DEFAULT_AVAILABLE_ATTEMPTS
from simcore_service_dynamic_scheduler.services.p_scheduler._errors import StepNotFoundError, StepNotInFailedError
from simcore_service_dynamic_scheduler.services.p_scheduler._models import RunId, Step, StepId, StepState
from simcore_service_dynamic_scheduler.services.p_scheduler._repositories import StepsRepository
from simcore_service_dynamic_scheduler.services.p_scheduler._repositories.steps import (
    _INITIAL_ATTEMPT_NUMBER,
    _row_to_step,
)
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


async def _assert_step_is_missing(engine: AsyncEngine, step_id: StepId) -> None:
    async with engine.connect() as conn:
        result = await conn.execute(sa.select("*").where(ps_steps.c.step_id == step_id))
    assert result.first() is None


async def _get_step_fail_history(engine: AsyncEngine, step_id: StepId) -> list[Row]:
    async with engine.connect() as conn:
        result = await conn.execute(sa.select("*").where(ps_step_fail_history.c.step_id == step_id))
    return result.fetchall()


async def _set_step_as_failed(engine: AsyncEngine, step_id: StepId) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            ps_steps.update()
            .where(ps_steps.c.step_id == step_id)
            .values(
                state=StepState.FAILED.value,
                finished_at=sa.func.now(),
                message="Step failed for testing",
            )
        )


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


@pytest.mark.parametrize("is_reverting", [False, True])
async def test_create_step(steps_repo: StepsRepository, run_id: RunId, is_reverting: bool):
    step = await steps_repo.create_step(
        run_id, _AStep.get_unique_reference(), step_class=_AStep, is_reverting=is_reverting
    )
    assert step.run_id == run_id
    assert step.available_attempts == _DEFAULT_AVAILABLE_ATTEMPTS
    assert step.attempt_number == _INITIAL_ATTEMPT_NUMBER

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


async def test_retry_failed_step(
    steps_repo: StepsRepository,
    engine: AsyncEngine,
    run_id: RunId,
    create_step_in_db: Callable[..., Awaitable[Step]],
    missing_step_id: StepId,
    number_of_steps: NonNegativeInt,
):
    # 1. step can be retried if in FAILED state
    message = "Step failed for testing retry"
    step = await create_step_in_db(state=StepState.FAILED, finished_at=sa.func.now(), message=message)

    await steps_repo.retry_failed_step(step.step_id)

    step_row = await _get_step_row(engine, step_id=step.step_id)
    assert StepState(step_row.state) == StepState.CREATED
    assert step_row.attempt_number == step.attempt_number + 1
    assert step_row.available_attempts == step.available_attempts - 1
    assert step_row.finished_at is None
    assert step_row.message is None

    fail_history = await _get_step_fail_history(engine, step.step_id)
    assert len(fail_history) == 1
    fail_history_entry = fail_history[0]
    assert fail_history_entry.attempt == step.attempt_number
    assert StepState(fail_history_entry.state) == StepState.FAILED
    assert isinstance(fail_history_entry.finished_at, datetime)
    assert fail_history_entry.message == message

    # 2. step cannot be retried if not in FAILED state
    with pytest.raises(StepNotInFailedError):
        await steps_repo.retry_failed_step(step.step_id)

    # 3. step cannot be retried if step_id does not exist
    with pytest.raises(StepNotInFailedError):
        await steps_repo.retry_failed_step(missing_step_id)

    # 4. reretrying a failed step adds more entries to history
    for k in range(number_of_steps):
        await _set_step_as_failed(engine, step.step_id)
        await steps_repo.retry_failed_step(step.step_id)

        fail_history = await _get_step_fail_history(engine, step.step_id)
        assert len(fail_history) == k + 2


@pytest.mark.parametrize("step_state", StepState)
async def test_manual_retry_step(
    steps_repo: StepsRepository,
    engine: AsyncEngine,
    run_id: RunId,
    create_step_in_db: Callable[..., Awaitable[Step]],
    missing_step_id: StepId,
    step_state: StepState,
):
    # 1. step can be manually retried if in FAILED state
    reason = "Step needs to be retried for testing"
    step = await create_step_in_db(state=step_state, finished_at=sa.func.now(), message=reason)

    await steps_repo.manual_retry_step(step.step_id, reason)

    step_row = await _get_step_row(engine, step_id=step.step_id)
    assert StepState(step_row.state) == StepState.CREATED
    assert step_row.attempt_number == step.attempt_number + 1
    assert step_row.available_attempts == step.available_attempts + 1
    assert step_row.finished_at is None

    fail_history = await _get_step_fail_history(engine, step.step_id)
    assert len(fail_history) == 1
    fail_history_entry = fail_history[0]
    assert fail_history_entry.attempt == step.attempt_number
    assert StepState(fail_history_entry.state) == step_state
    assert isinstance(fail_history_entry.finished_at, datetime)
    assert fail_history_entry.message == f"Manual RETRY: {reason}"

    # 2. step cannot be manually retried if step_id does not exist
    with pytest.raises(StepNotFoundError):
        await steps_repo.manual_retry_step(missing_step_id, reason)


@pytest.mark.parametrize("step_state", StepState)
async def test_manual_skip_step(
    steps_repo: StepsRepository,
    engine: AsyncEngine,
    run_id: RunId,
    create_step_in_db: Callable[..., Awaitable[Step]],
    missing_step_id: StepId,
    step_state: StepState,
):
    # 1. step can be skipped
    reason = "Step needs to be skipped for testing"
    step = await create_step_in_db(state=step_state)

    await steps_repo.manual_skip_step(step.step_id, reason)

    step_row = await _get_step_row(engine, step_id=step.step_id)
    assert StepState(step_row.state) == StepState.SKIPPED
    assert step_row.message == f"Manual SKIP: {reason}"

    # 2. step cannot be skipped if step_id does not exist
    with pytest.raises(StepNotFoundError):
        await steps_repo.manual_skip_step(missing_step_id, reason)


async def test_set_step_as_ready(
    steps_repo: StepsRepository,
    engine: AsyncEngine,
    run_id: RunId,
    create_step_in_db: Callable[..., Awaitable[Step]],
    missing_step_id: StepId,
):
    # 1. step can be set as ready if in CREATED state
    step = await create_step_in_db(state=StepState.CREATED)

    await steps_repo.set_step_as_ready(step.step_id)

    step_row = await _get_step_row(engine, step_id=step.step_id)
    assert StepState(step_row.state) == StepState.READY

    # 2. step cannot be set as ready if not in CREATED state
    for state in set(StepState) - {StepState.CREATED}:
        step = await create_step_in_db(state=state)
        await steps_repo.set_step_as_ready(step.step_id)

        step_row = await _get_step_row(engine, step_id=step.step_id)
        assert StepState(step_row.state) == state

    # 3. step cannot be set as ready if step_id does not exist
    await steps_repo.set_step_as_ready(missing_step_id)
    await _assert_step_is_missing(engine, missing_step_id)


async def test_get_step_for_workflow_manager(
    steps_repo: StepsRepository,
    engine: AsyncEngine,
    run_id: RunId,
    create_step_in_db: Callable[..., Awaitable[Step]],
    missing_step_id: StepId,
):
    # 1. step can be retrieved if it exists
    step = await create_step_in_db()

    retrieved_step = await steps_repo.get_step_for_workflow_manager(step.step_id)
    assert retrieved_step == step

    # 2. None is returned if step_id does not exist
    assert await steps_repo.get_step_for_workflow_manager(missing_step_id) is None


async def test_acquire_running_step_for_worker(
    steps_repo: StepsRepository,
    engine: AsyncEngine,
    run_id: RunId,
    create_step_in_db: Callable[..., Awaitable[Step]],
    missing_step_id: StepId,
):
    step = await create_step_in_db(state=StepState.READY)

    # 1. Nothing is returns if the steps is missing but a READY step exists
    assert await steps_repo.acquire_running_step_for_worker(missing_step_id) is None

    # 2. step can be retrieved if it exists
    retrieved_step = await steps_repo.acquire_running_step_for_worker(step.step_id)
    expected_step = deepcopy(step)
    expected_step.state = StepState.RUNNING
    assert retrieved_step == expected_step
    # no more steps to return
    assert await steps_repo.acquire_running_step_for_worker(step.step_id) is None

    # 3. Not Ready steps are never returned
    for state in set(StepState) - {StepState.READY}:
        step = await create_step_in_db(state=state)
        assert await steps_repo.acquire_running_step_for_worker(step.step_id) is None


@pytest.mark.parametrize("step_state", StepState)
async def test_set_step_as_cancelled(
    steps_repo: StepsRepository,
    engine: AsyncEngine,
    run_id: RunId,
    create_step_in_db: Callable[..., Awaitable[Step]],
    missing_step_id: StepId,
    step_state: StepState,
):
    # 1. step can be set as cancelled if it exists
    step = await create_step_in_db(state=step_state)

    await steps_repo.set_step_as_cancelled(step.step_id)

    step_row = await _get_step_row(engine, step_id=step.step_id)
    assert StepState(step_row.state) == StepState.CANCELLED

    # 2. step cannot be set as cancelled if step_id does not exist
    await steps_repo.set_step_as_cancelled(missing_step_id)
    await _assert_step_is_missing(engine, missing_step_id)


@pytest.mark.parametrize("step_state", StepState)
async def test_set_step_as_success(
    steps_repo: StepsRepository,
    engine: AsyncEngine,
    run_id: RunId,
    create_step_in_db: Callable[..., Awaitable[Step]],
    missing_step_id: StepId,
    step_state: StepState,
):
    # 1. step can be set as success if it exists
    step = await create_step_in_db(state=step_state)

    await steps_repo.set_step_as_success(step.step_id)

    step_row = await _get_step_row(engine, step_id=step.step_id)
    assert StepState(step_row.state) == StepState.SUCCESS

    # 2. step cannot be set as success if step_id does not exist
    await steps_repo.set_step_as_success(missing_step_id)
    await _assert_step_is_missing(engine, missing_step_id)


@pytest.mark.parametrize("step_state", StepState)
async def test_set_step_as_failed(
    steps_repo: StepsRepository,
    engine: AsyncEngine,
    run_id: RunId,
    create_step_in_db: Callable[..., Awaitable[Step]],
    missing_step_id: StepId,
    step_state: StepState,
):
    # 1. step can be set as failed if it exists
    message = "Step failed for testing"
    step = await create_step_in_db(state=step_state)

    await steps_repo.set_step_as_failed(step.step_id, message)

    step_row = await _get_step_row(engine, step_id=step.step_id)
    assert StepState(step_row.state) == StepState.FAILED
    assert step_row.message == message

    # 2. step cannot be set as failed if step_id does not exist
    await steps_repo.set_step_as_failed(missing_step_id, message)
    await _assert_step_is_missing(engine, missing_step_id)
