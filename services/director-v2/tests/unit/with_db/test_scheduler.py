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
from simcore_service_director_v2.models.domains.comp_tasks import Image
from simcore_service_director_v2.modules.celery import CeleryClient
from simcore_service_director_v2.modules.scheduler import (
    _SCHEDULED_STATES,
    Scheduler,
    _runtime_requirement,
    scheduler_task,
)

# 1. setup database
# 2. setup tables
# 3. init scheduler, it should be empty
# 4. create a project, set some pipeline, tasks
# 5. based on the task states, the scheduler should schedule,
# or stop, or mark as failed, aborted.


#####################333
# Rationale
#
# 1. each time the Play button is pressed, a new comp_run entry is inserted
# 2. ideally, on play a snapshot of the workbench should be created, such that the scheduler can schedule
# 3. each time a task is completed, it should return its results, retrieves them, and updates the databases instead of the sidecar
# 4. each time completes, the scheduler starts the next one or aborts it in case of failure or cancellation
#
pytest_simcore_core_services_selection = ["postgres", "redis", "rabbit"]
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
    "image, exp_requirement",
    [
        (
            Image(
                name="simcore/services/dynamic/fake",
                tag="1.2.3",
                requires_gpu=False,
                requires_mpi=False,
            ),
            "cpu",
        ),
        (
            Image(
                name="simcore/services/dynamic/fake",
                tag="1.2.3",
                requires_gpu=True,
                requires_mpi=False,
            ),
            "gpu",
        ),
        (
            Image(
                name="simcore/services/dynamic/fake",
                tag="1.2.3",
                requires_gpu=False,
                requires_mpi=True,
            ),
            "mpi",
        ),
        (
            # FIXME: What should happen here??
            Image(
                name="simcore/services/dynamic/fake",
                tag="1.2.3",
                requires_gpu=True,
                requires_mpi=True,
            ),
            "gpu",
        ),
    ],
)
def test_scheduler_correctly_defines_runtime_requirements(
    image: Image, exp_requirement: str
):
    assert _runtime_requirement(image) == exp_requirement


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
        await Scheduler.create_from_db(incorectly_configured_app)

    # missing celery client
    incorectly_configured_app = FakeApp(
        state=FakeState(engine=aiopg_engine, celery_client=None)
    )
    del incorectly_configured_app.state.celery_client
    with pytest.raises(ConfigurationError):
        await Scheduler.create_from_db(incorectly_configured_app)

    # now should be ok
    correctly_configured_app = FakeApp(
        state=FakeState(
            engine=aiopg_engine,
            celery_client=celery_client,
        )
    )
    await Scheduler.create_from_db(correctly_configured_app)


async def test_scheduler_initializes_with_correct_state(
    fake_app: FakeApp,
):
    scheduler = await Scheduler.create_from_db(fake_app)


async def test_scheduler_task_starts_and_stops_gracefully(fake_app: FakeApp):
    task = asyncio.get_event_loop().create_task(scheduler_task(fake_app))
    # let it run
    await asyncio.sleep(3)
    # now check the scheduler was registered correctly
    assert fake_app.state.scheduler is not None
    # stop the scheduler gracefully
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert fake_app.state.scheduler is None
