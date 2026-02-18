# pylint:disable=contextmanager-generator-missing-cleanup
# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

from collections.abc import Callable

import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from models_library.projects_nodes_io import NodeID
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.postgres_tools import (
    PostgresTestConfig,
)
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_service_dynamic_scheduler.services.base_repository import (
    get_repository,
)
from simcore_service_dynamic_scheduler.services.p_scheduler._errors import RunAlreadyExistsError
from simcore_service_dynamic_scheduler.services.p_scheduler._models import Run, RunId
from simcore_service_dynamic_scheduler.services.p_scheduler._repositories import RunsRepository
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
def runs_repo(app: FastAPI) -> RunsRepository:
    return get_repository(app, RunsRepository)


async def test_get_run_from_node_id(
    runs_repo: RunsRepository,
    missing_node_id: NodeID,
    node_id: NodeID,
    ps_run_in_db: Run,
):
    assert await runs_repo.get_run_from_node_id(missing_node_id) is None
    assert await runs_repo.get_run_from_node_id(node_id) == ps_run_in_db


async def test_get_run(
    runs_repo: RunsRepository,
    missing_run_id: RunId,
    run_id: RunId,
    ps_run_in_db: Run,
):
    assert await runs_repo.get_run(missing_run_id) is None
    assert await runs_repo.get_run(run_id) == ps_run_in_db


async def test_create_from_start_request(
    runs_repo: RunsRepository,
    missing_node_id: NodeID,
    auto_remove_ps_runs: Callable[[Run | RunId], None],
    node_id: NodeID,
):
    run = await runs_repo.create_from_start_request(node_id=missing_node_id)
    auto_remove_ps_runs(run)
    assert run.node_id == missing_node_id
    assert run.workflow_name == "START"
    assert run.is_reverting is False
    assert run.waiting_manual_intervention is False

    with pytest.raises(RunAlreadyExistsError):
        await runs_repo.create_from_start_request(node_id=node_id)


async def test_create_from_stop_request(
    runs_repo: RunsRepository,
    missing_node_id: NodeID,
    auto_remove_ps_runs: Callable[[Run | RunId], None],
    node_id: NodeID,
):
    run = await runs_repo.create_from_stop_request(node_id=missing_node_id)
    auto_remove_ps_runs(run)

    assert run.node_id == missing_node_id
    assert run.workflow_name == "STOP"
    assert run.is_reverting is True
    assert run.waiting_manual_intervention is False

    with pytest.raises(RunAlreadyExistsError):
        await runs_repo.create_from_stop_request(node_id=node_id)


async def test_cancel_run(runs_repo: RunsRepository, missing_run_id: RunId, run_id: RunId):
    await runs_repo.cancel_run(missing_run_id)
    await runs_repo.cancel_run(run_id)


async def test_set_waiting_manual_intervention(runs_repo: RunsRepository, missing_run_id: RunId, run_id: RunId):
    await runs_repo.set_waiting_manual_intervention(missing_run_id)
    await runs_repo.set_waiting_manual_intervention(run_id)


async def test_remove_run(runs_repo: RunsRepository, missing_run_id: RunId, run_id: RunId):
    await runs_repo.remove_run(missing_run_id)
    await runs_repo.remove_run(run_id)


async def test_get_all_runs(runs_repo: RunsRepository, ps_run_in_db: Run):
    all_runs = await runs_repo.get_all_runs()
    assert all_runs == [ps_run_in_db]

    await runs_repo.remove_run(ps_run_in_db.run_id)
    assert await runs_repo.get_all_runs() == []
