# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access
# pylint:disable=no-value-for-parameter
# pylint:disable=too-many-arguments


import asyncio
from dataclasses import dataclass
from typing import Any, Dict, Iterator

import aiopg
import pytest
import sqlalchemy as sa
from _pytest.monkeypatch import MonkeyPatch
from celery import Celery
from fastapi.applications import FastAPI
from models_library.settings.celery import CeleryConfig
from models_library.settings.rabbit import RabbitConfig
from models_library.settings.redis import RedisConfig
from settings_library.celery import CelerySettings
from simcore_service_director_v2.core.errors import ConfigurationError
from simcore_service_director_v2.core.settings import CelerySchedulerSettings
from simcore_service_director_v2.modules.celery import CeleryClient
from simcore_service_director_v2.modules.comp_scheduler.background_task import (
    scheduler_task,
)
from simcore_service_director_v2.modules.comp_scheduler.factory import create_from_db

pytest_simcore_core_services_selection = ["postgres", "redis", "rabbit"]
pytest_simcore_ops_services_selection = ["adminer", "redis-commander"]


@pytest.fixture
def minimal_celery_scheduler_config(
    project_env_devel_environment: Dict[str, Any], monkeypatch: MonkeyPatch
) -> None:
    """set a minimal configuration for testing the dask connection only"""
    monkeypatch.setenv("DIRECTOR_V2_POSTGRES_ENABLED", "1")
    monkeypatch.setenv("DIRECTOR_V2_DYNAMIC_SIDECAR_ENABLED", "false")
    monkeypatch.setenv("DIRECTOR_V0_ENABLED", "0")
    monkeypatch.setenv("DIRECTOR_V2_POSTGRES_ENABLED", "0")
    monkeypatch.setenv("DIRECTOR_V2_CELERY_ENABLED", "0")
    monkeypatch.setenv("DIRECTOR_V2_CELERY_SCHEDULER_ENABLED", "1")
    monkeypatch.setenv("DIRECTOR_V2_DASK_CLIENT_ENABLED", "0")
    monkeypatch.setenv("DIRECTOR_V2_DASK_SCHEDULER_ENABLED", "0")


def test_scheduler_starts(
    postgres_host_config: Dict[str, str],
    aiopg_engine: Iterator[aiopg.sa.engine.Engine],
    minimal_celery_scheduler_config: None,
    minimal_app: FastAPI,
):
    pass


@dataclass
class FakeSettings:
    CELERY_SCHEDULER = CelerySchedulerSettings()
    DIRECTOR_V2_DEV_FEATURES_ENABLED: bool = False


@dataclass
class FakeState:
    engine: sa.engine.Engine
    celery_client: CeleryClient
    settings = FakeSettings()


@dataclass
class FakeApp:
    state: FakeState


@pytest.fixture()
def celery_config(
    redis_service: RedisConfig, rabbit_service: RabbitConfig
) -> CelerySettings:
    return CelerySettings()


@pytest.fixture()
def celery_client(celery_config: CelerySettings) -> CeleryClient:
    return CeleryClient(
        client=Celery(
            celery_config.CELERY_TASK_NAME,
            broker=celery_config.broker_url,
            backend=celery_config.result_backend,
        ),
        settings=celery_config,
    )


@pytest.fixture()
def fake_app(
    aiopg_engine: sa.engine.Engine,
    postgres_host_config: Dict[str, Any],
    celery_client: CeleryClient,
) -> FakeApp:

    return FakeApp(state=FakeState(engine=aiopg_engine, celery_client=celery_client))


# async def test_scheduler_throws_error_for_missing_dependencies(
#     aiopg_engine: sa.engine.Engine,
#     postgres_host_config: Dict[str, Any],
#     celery_client: CeleryClient,
# ):
#     # missing db engine
#     incorectly_configured_app = FakeApp(state=None)
#     with pytest.raises(ConfigurationError):
#         await create_from_db(incorectly_configured_app)

#     # missing celery client
#     incorectly_configured_app = FakeApp(
#         state=FakeState(engine=aiopg_engine, celery_client=None)
#     )
#     del incorectly_configured_app.state.celery_client
#     with pytest.raises(ConfigurationError):
#         await create_from_db(incorectly_configured_app)

#     # now should be ok
#     correctly_configured_app = FakeApp(
#         state=FakeState(
#             engine=aiopg_engine,
#             celery_client=celery_client,
#         )
#     )
#     await create_from_db(correctly_configured_app)


# async def test_scheduler_initializes_without_error(
#     fake_app: FakeApp,
# ):
#     await create_from_db(fake_app)


# async def test_scheduler_task_starts_and_stops_gracefully(fake_app: FakeApp):
#     scheduler = await create_from_db(fake_app)
#     task = asyncio.get_event_loop().create_task(scheduler_task(scheduler))
#     # let it run
#     await asyncio.sleep(3)
#     # stop the scheduler gracefully
#     task.cancel()
#     with pytest.raises(asyncio.CancelledError):
#         await task
