# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=no-value-for-parameter
# pylint:disable=protected-access
# pylint:disable=too-many-arguments
# pylint:disable=no-name-in-module
# pylint: disable=too-many-statements


import asyncio
from typing import Any, AsyncIterator, Awaitable, Callable
from unittest import mock

import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from models_library.projects import ProjectAtDB
from pytest_mock.plugin import MockerFixture
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from servicelib.rabbitmq._client import RabbitMQClient
from servicelib.redis import CouldNotAcquireLockError
from settings_library.rabbit import RabbitSettings
from settings_library.redis import RedisSettings
from simcore_postgres_database.models.comp_runs import comp_runs
from simcore_service_director_v2.models.comp_pipelines import CompPipelineAtDB
from simcore_service_director_v2.models.comp_runs import CompRunsAtDB
from simcore_service_director_v2.models.comp_tasks import CompTaskAtDB
from simcore_service_director_v2.modules.comp_scheduler._distributed_scheduler import (
    schedule_pipelines,
)
from simcore_service_director_v2.modules.comp_scheduler._models import (
    SchedulePipelineRabbitMessage,
)
from sqlalchemy.ext.asyncio import AsyncEngine

pytest_simcore_core_services_selection = ["postgres", "rabbit", "redis"]
pytest_simcore_ops_services_selection = [
    "adminer",
]


@pytest.fixture
def mock_env(
    mock_env: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
    fake_s3_envs: EnvVarsDict,
    postgres_db: sa.engine.Engine,
    postgres_host_config: dict[str, str],
    rabbit_service: RabbitSettings,
    redis_service: RedisSettings,
) -> EnvVarsDict:
    return mock_env | setenvs_from_dict(
        monkeypatch,
        {k: f"{v}" for k, v in fake_s3_envs.items()}
        | {
            "COMPUTATIONAL_BACKEND_ENABLED": True,
            "COMPUTATIONAL_BACKEND_DASK_CLIENT_ENABLED": True,
        },
    )


@pytest.fixture
async def scheduler_rabbit_client_parser(
    create_rabbitmq_client: Callable[[str], RabbitMQClient], mocker: MockerFixture
) -> AsyncIterator[mock.AsyncMock]:
    client = create_rabbitmq_client("scheduling_pytest_consumer")
    mock = mocker.AsyncMock(return_value=True)
    queue_name = await client.subscribe(
        SchedulePipelineRabbitMessage.get_channel_name(), mock
    )
    yield mock
    await client.unsubscribe(queue_name)


async def test_schedule_pipelines_empty_db(
    initialized_app: FastAPI,
    scheduler_rabbit_client_parser: mock.AsyncMock,
    sqlalchemy_async_engine: AsyncEngine,
):
    # check comp_runs is empty
    async with sqlalchemy_async_engine.connect() as conn:
        total_number_of_items = await conn.scalar(
            sa.select(sa.func.count()).select_from(comp_runs)
        )
    assert total_number_of_items == 0

    await schedule_pipelines(initialized_app)

    # check nothing was distributed
    scheduler_rabbit_client_parser.assert_not_called()

    # check comp_runs is still empty
    async with sqlalchemy_async_engine.connect() as conn:
        total_number_of_items = await conn.scalar(
            sa.select(sa.func.count()).select_from(comp_runs)
        )
    assert total_number_of_items == 0


async def test_schedule_pipelines_concurently_raises_and_only_one_runs(
    initialized_app: FastAPI,
):
    CONCURRENCY = 5
    # TODO: this can be flaky as an empty scheduling is very short
    with pytest.raises(
        CouldNotAcquireLockError,
        match=".+ computational-distributed-scheduler",
    ):
        await asyncio.gather(
            *(schedule_pipelines(initialized_app) for _ in range(CONCURRENCY))
        )

    results = await asyncio.gather(
        *(schedule_pipelines(initialized_app) for _ in range(CONCURRENCY)),
        return_exceptions=True,
    )

    assert results.count(None) == 1, "Only one task should have run"


async def test_schedule_pipelines_with_runs(
    registered_user: Callable[..., dict[str, Any]],
    project: Callable[..., Awaitable[ProjectAtDB]],
    pipeline: Callable[..., CompPipelineAtDB],
    tasks: Callable[..., list[CompTaskAtDB]],
    runs: Callable[..., CompRunsAtDB],
):
    user = registered_user()
    proj = await project(user, workbench=fake_workbench_without_outputs)
    pipeline(
        project_id=proj.uuid,
        dag_adjacency_list=fake_workbench_adjacency,
    )
    comp_tasks = tasks(user=user, project=proj, state=StateType.PUBLISHED, progress=0)
    comp_runs = runs(user=user, project=proj, result=StateType.PUBLISHED)
