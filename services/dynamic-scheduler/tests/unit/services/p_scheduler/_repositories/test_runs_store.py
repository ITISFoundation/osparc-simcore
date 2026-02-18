# pylint:disable=contextmanager-generator-missing-cleanup
# pylint:disable=redefined-outer-name
# pylint:disable=too-many-arguments
# pylint:disable=unused-argument


from typing import Any

import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.postgres_tools import (
    PostgresTestConfig,
)
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_service_dynamic_scheduler.services.base_repository import (
    get_repository,
)
from simcore_service_dynamic_scheduler.services.p_scheduler._models import RunId
from simcore_service_dynamic_scheduler.services.p_scheduler._repositories import RunsStoreRepository
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
def runs_store_repo(app: FastAPI) -> RunsStoreRepository:
    return get_repository(app, RunsStoreRepository)


@pytest.mark.parametrize(
    "data, queried_keys",
    [
        ({}, set()),
        ({"k1": "v1", "k2": 2}, {"k1"}),
        ({"k1": "v1", "k2": 2}, {"k1", "k2"}),
    ],
)
async def test_runs_store_workflow(
    runs_store_repo: RunsStoreRepository, run_id: RunId, data: dict[str, Any], queried_keys: set[str]
) -> None:
    assert await runs_store_repo.get_from_store(run_id, queried_keys) == {}
    await runs_store_repo.set_to_store(run_id, data)
    assert await runs_store_repo.get_from_store(run_id, queried_keys) == {
        k: v for k, v in data.items() if k in queried_keys
    }


async def test_runs_store_missing_run_id(runs_store_repo: RunsStoreRepository, missing_run_id: RunId) -> None:
    missing_run_id = -42
    assert await runs_store_repo.get_from_store(missing_run_id, {"k1", "k2"}) == {}
