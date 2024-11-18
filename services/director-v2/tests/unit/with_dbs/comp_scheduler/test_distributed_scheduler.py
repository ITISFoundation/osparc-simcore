# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=no-value-for-parameter
# pylint:disable=protected-access
# pylint:disable=too-many-arguments
# pylint:disable=no-name-in-module
# pylint: disable=too-many-statements


import asyncio
from collections.abc import AsyncIterator, Callable
from unittest import mock

import pytest
import sqlalchemy as sa
from _helpers import PublishedProject
from fastapi import FastAPI
from models_library.clusters import DEFAULT_CLUSTER_ID
from pytest_mock.plugin import MockerFixture
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from servicelib.rabbitmq._client import RabbitMQClient
from servicelib.redis import CouldNotAcquireLockError
from servicelib.utils import limited_gather
from settings_library.rabbit import RabbitSettings
from settings_library.redis import RedisSettings
from simcore_postgres_database.models.comp_runs import comp_runs
from simcore_service_director_v2.models.comp_runs import CompRunsAtDB, RunMetadataDict
from simcore_service_director_v2.modules.comp_scheduler._distributed_scheduler import (
    run_new_pipeline,
    schedule_pipelines,
)
from simcore_service_director_v2.modules.comp_scheduler._models import (
    SchedulePipelineRabbitMessage,
)
from sqlalchemy.ext.asyncio import AsyncEngine

pytest_simcore_core_services_selection = ["postgres", "rabbit", "redis"]
pytest_simcore_ops_services_selection = ["adminer", "redis-commander"]


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


async def _assert_comp_runs(
    sqlalchemy_async_engine: AsyncEngine, *, expected_total: int
) -> list[CompRunsAtDB]:
    async with sqlalchemy_async_engine.connect() as conn:
        list_of_comp_runs = [
            CompRunsAtDB.from_orm(row)
            for row in await conn.execute(sa.select(comp_runs))
        ]
    assert len(list_of_comp_runs) == expected_total
    return list_of_comp_runs


async def _assert_comp_runs_empty(sqlalchemy_async_engine: AsyncEngine) -> None:
    await _assert_comp_runs(sqlalchemy_async_engine, expected_total=0)


async def test_schedule_pipelines_empty_db(
    initialized_app: FastAPI,
    scheduler_rabbit_client_parser: mock.AsyncMock,
    sqlalchemy_async_engine: AsyncEngine,
):
    await _assert_comp_runs_empty(sqlalchemy_async_engine)

    await schedule_pipelines(initialized_app)

    # check nothing was distributed
    scheduler_rabbit_client_parser.assert_not_called()

    # check comp_runs is still empty
    await _assert_comp_runs_empty(sqlalchemy_async_engine)


async def test_schedule_pipelines_concurently_runs_exclusively_and_raises(
    initialized_app: FastAPI, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
):
    CONCURRENCY = 5
    # NOTE: this ensure no flakyness as empty scheduling is very fast
    original_function = limited_gather

    async def slow_limited_gather(*args, **kwargs):
        result = await original_function(*args, **kwargs)
        await asyncio.sleep(3)  # to ensure flakyness does not occur
        return result

    mock_function = mocker.patch(
        "simcore_service_director_v2.modules.comp_scheduler._distributed_scheduler.limited_gather",
        autospec=True,
        side_effect=slow_limited_gather,
    )

    results = await asyncio.gather(
        *(schedule_pipelines(initialized_app) for _ in range(CONCURRENCY)),
        return_exceptions=True,
    )

    assert results.count(None) == 1, f"Only one task should have run: {results}"
    for r in results:
        if r:
            assert isinstance(r, CouldNotAcquireLockError)
    mock_function.assert_called_once()


async def test_schedule_pipelines_with_non_scheduled_runs(
    initialized_app: FastAPI,
    published_project: PublishedProject,
    sqlalchemy_async_engine: AsyncEngine,
    run_metadata: RunMetadataDict,
    scheduler_rabbit_client_parser: mock.AsyncMock,
):
    await _assert_comp_runs_empty(sqlalchemy_async_engine)
    assert published_project.project.prj_owner
    # now we schedule a pipeline
    await run_new_pipeline(
        initialized_app,
        user_id=published_project.project.prj_owner,
        project_id=published_project.project.uuid,
        cluster_id=DEFAULT_CLUSTER_ID,
        run_metadata=run_metadata,
        use_on_demand_clusters=False,
    )
    scheduler_rabbit_client_parser.assert_called_once_with(
        SchedulePipelineRabbitMessage(
            user_id=published_project.project.prj_owner,
            project_id=published_project.project.uuid,
            iteration=1,
        ).body()
    )
    comp_runs = await _assert_comp_runs(sqlalchemy_async_engine, expected_total=1)
