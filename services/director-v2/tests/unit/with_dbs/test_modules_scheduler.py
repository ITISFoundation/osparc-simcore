# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access
# pylint:disable=no-value-for-parameter
# pylint:disable=too-many-arguments


import asyncio
from dataclasses import dataclass
from typing import Any, Dict

import pytest
import sqlalchemy as sa
from celery import Celery
from models_library.projects_state import RunningState
from models_library.settings.celery import CeleryConfig
from models_library.settings.rabbit import RabbitConfig
from models_library.settings.redis import RedisConfig
from simcore_service_director_v2.core.errors import ConfigurationError
from simcore_service_director_v2.modules.celery import CeleryClient
from simcore_service_director_v2.modules.scheduler import (
    _COMPLETED_STATES,
    _SCHEDULED_STATES,
    CeleryScheduler,
    scheduler_task,
)

pytest_simcore_core_services_selection = ["migration", "postgres", "redis", "rabbit"]
pytest_simcore_ops_services_selection = ["adminer", "redis-commander"]


@pytest.mark.parametrize(
    "state",
    [
        RunningState.PUBLISHED,
        RunningState.PENDING,
        RunningState.STARTED,
        RunningState.RETRY,
    ],
)
def test_scheduler_takes_care_of_runs_with_state(state: RunningState):
    assert state in _SCHEDULED_STATES


@pytest.mark.parametrize(
    "state",
    [
        RunningState.SUCCESS,
        RunningState.ABORTED,
        RunningState.FAILED,
    ],
)
def test_scheduler_knows_these_are_completed_states(state: RunningState):
    assert state in _COMPLETED_STATES


def test_scheduler_knows_all_the_states():
    assert _COMPLETED_STATES.union(_SCHEDULED_STATES).union(
        {RunningState.NOT_STARTED, RunningState.UNKNOWN}
    ) == set(RunningState)


@dataclass
class FakeState:
    engine: sa.engine.Engine
    celery_client: CeleryClient


@dataclass
class FakeApp:
    state: FakeState


@pytest.fixture()
def celery_config(
    redis_service: RedisConfig, rabbit_service: RabbitConfig
) -> CeleryConfig:
    return CeleryConfig.create_from_env()


@pytest.fixture()
def celery_client(celery_config: CeleryConfig) -> CeleryClient:
    return (
        CeleryClient(
            client=Celery(
                celery_config.task_name,
                broker=celery_config.broker_url,
                backend=celery_config.result_backend,
            ),
            settings=celery_config,
        ),
    )


@pytest.fixture()
def fake_app(
    aiopg_engine: sa.engine.Engine,
    postgres_host_config: Dict[str, Any],
    celery_client: CeleryClient,
) -> FakeApp:

    return FakeApp(state=FakeState(engine=aiopg_engine, celery_client=celery_client))


async def test_scheduler_throws_error_for_missing_dependencies(
    aiopg_engine: sa.engine.Engine,
    postgres_host_config: Dict[str, Any],
    celery_client: CeleryClient,
):
    # missing db engine
    incorectly_configured_app = FakeApp(state=None)
    with pytest.raises(ConfigurationError):
        await CeleryScheduler.create_from_db(incorectly_configured_app)

    # missing celery client
    incorectly_configured_app = FakeApp(
        state=FakeState(engine=aiopg_engine, celery_client=None)
    )
    del incorectly_configured_app.state.celery_client
    with pytest.raises(ConfigurationError):
        await CeleryScheduler.create_from_db(incorectly_configured_app)

    # now should be ok
    correctly_configured_app = FakeApp(
        state=FakeState(
            engine=aiopg_engine,
            celery_client=celery_client,
        )
    )
    await CeleryScheduler.create_from_db(correctly_configured_app)


async def test_scheduler_initializes_without_error(
    fake_app: FakeApp,
):
    await CeleryScheduler.create_from_db(fake_app)


async def test_scheduler_task_starts_and_stops_gracefully(fake_app: FakeApp):
    scheduler = await CeleryScheduler.create_from_db(fake_app)
    task = asyncio.get_event_loop().create_task(scheduler_task(scheduler))
    # let it run
    await asyncio.sleep(3)
    # stop the scheduler gracefully
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
