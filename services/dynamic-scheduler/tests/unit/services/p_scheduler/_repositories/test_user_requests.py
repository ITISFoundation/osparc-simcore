# pylint:disable=contextmanager-generator-missing-cleanup
# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument


import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from models_library.api_schemas_dynamic_scheduler.dynamic_services import DynamicServiceStart, DynamicServiceStop
from models_library.projects_nodes_io import NodeID
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.postgres_tools import PostgresTestConfig
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_service_dynamic_scheduler.services.base_repository import (
    get_repository,
)
from simcore_service_dynamic_scheduler.services.p_scheduler._models import UserDesiredState
from simcore_service_dynamic_scheduler.services.p_scheduler._repositories import UserRequestsRepository
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
def user_requests_repo(app: FastAPI) -> UserRequestsRepository:
    return get_repository(app, UserRequestsRepository)


async def _assert_service_present(
    user_requests_repo: UserRequestsRepository, dynamic_service_start: DynamicServiceStart, node_id: NodeID
) -> None:
    await user_requests_repo.request_service_present(dynamic_service_start)

    user_request = await user_requests_repo.get_user_request(node_id)
    assert user_request is not None
    assert user_request.user_desired_state == UserDesiredState.PRESENT
    assert user_request.payload == dynamic_service_start


async def _assert_service_absent(
    user_requests_repo: UserRequestsRepository, dynamic_service_stop: DynamicServiceStop, node_id: NodeID
) -> None:
    await user_requests_repo.request_service_absent(dynamic_service_stop)

    user_request = await user_requests_repo.get_user_request(node_id)
    assert user_request is not None
    assert user_request.user_desired_state == UserDesiredState.ABSENT
    assert user_request.payload == dynamic_service_stop


async def test_get_user_request_not_found(user_requests_repo: UserRequestsRepository, missing_node_id: NodeID) -> None:
    user_request = await user_requests_repo.get_user_request(missing_node_id)
    assert user_request is None


async def test_request_service_seqnece_presnet_absent_present(
    dynamic_service_start: DynamicServiceStart,
    dynamic_service_stop: DynamicServiceStop,
    user_requests_repo: UserRequestsRepository,
    node_id: NodeID,
) -> None:
    await _assert_service_present(user_requests_repo, dynamic_service_start, node_id)
    await _assert_service_absent(user_requests_repo, dynamic_service_stop, node_id)
    await _assert_service_present(user_requests_repo, dynamic_service_start, node_id)


async def test_request_service_seqnece_absent_presnet_absent(
    dynamic_service_start: DynamicServiceStart,
    dynamic_service_stop: DynamicServiceStop,
    user_requests_repo: UserRequestsRepository,
    node_id: NodeID,
) -> None:
    await _assert_service_absent(user_requests_repo, dynamic_service_stop, node_id)
    await _assert_service_present(user_requests_repo, dynamic_service_start, node_id)
    await _assert_service_absent(user_requests_repo, dynamic_service_stop, node_id)
