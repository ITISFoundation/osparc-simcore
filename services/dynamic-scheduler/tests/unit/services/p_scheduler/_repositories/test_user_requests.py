# pylint:disable=contextmanager-generator-missing-cleanup
# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import AsyncExitStack
from typing import Any

import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from models_library.api_schemas_dynamic_scheduler.dynamic_services import DynamicServiceStart, DynamicServiceStop
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.users import UserID
from pydantic import TypeAdapter
from pytest_simcore.helpers.faker_factories import random_product, random_project, random_user
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.postgres_tools import (
    PostgresTestConfig,
    insert_and_get_row_lifespan,
)
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_postgres_database.models.products import products
from simcore_postgres_database.models.projects import projects
from simcore_postgres_database.models.users import users
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


@pytest.fixture
async def create_user(
    sqlalchemy_async_engine: AsyncEngine,
) -> AsyncIterator[Callable[..., Awaitable[dict[str, Any]]]]:
    stack = AsyncExitStack()

    async def _(**overrides) -> dict[str, Any]:
        ctx = insert_and_get_row_lifespan(
            sqlalchemy_async_engine,
            table=users,
            values=random_user(**overrides),
            pk_col=users.c.id,
        )
        return await stack.enter_async_context(ctx)

    yield _

    await stack.aclose()


@pytest.fixture
async def create_product(
    sqlalchemy_async_engine: AsyncEngine,
) -> AsyncIterator[Callable[..., Awaitable[dict[str, Any]]]]:
    stack = AsyncExitStack()

    async def _(**overrides) -> dict[str, Any]:
        ctx = insert_and_get_row_lifespan(
            sqlalchemy_async_engine,
            table=products,
            values=random_product(**overrides),
            pk_col=products.c.name,
        )
        return await stack.enter_async_context(ctx)

    yield _

    await stack.aclose()


@pytest.fixture
async def create_project(
    sqlalchemy_async_engine: AsyncEngine,
) -> AsyncIterator[Callable[..., Awaitable[dict[str, Any]]]]:
    async with AsyncExitStack() as stack:

        async def _(**overrides) -> dict[str, Any]:
            ctx = insert_and_get_row_lifespan(
                sqlalchemy_async_engine,
                table=projects,
                values=random_project(**overrides),
                pk_col=projects.c.uuid,
            )
            return await stack.enter_async_context(ctx)

        yield _


@pytest.fixture
async def user_id(create_user: Callable[..., Awaitable[dict[str, Any]]]) -> UserID:
    user = await create_user()
    return user["id"]


@pytest.fixture
async def product_name(create_product: Callable[..., Awaitable[dict[str, Any]]]) -> ProductName:
    product = await create_product()
    return product["name"]


@pytest.fixture
async def project_id(
    user_id: UserID, product_name: ProductName, create_project: Callable[..., Awaitable[dict[str, Any]]]
) -> ProjectID:
    project = await create_project(prj_owner=user_id, product_name=product_name)
    return project["uuid"]


@pytest.fixture
async def dynamic_service_start(
    user_id: UserID,
    product_name: ProductName,
    project_id: ProjectID,
    node_id: NodeID,
) -> DynamicServiceStart:
    return TypeAdapter(DynamicServiceStart).validate_python(
        DynamicServiceStart.model_json_schema()["example"]
        | {
            "product_name": product_name,
            "user_id": user_id,
            "project_id": project_id,
            "service_uuid": f"{node_id}",
        }
    )


@pytest.fixture
async def dynamic_service_stop(
    user_id: UserID,
    product_name: ProductName,
    project_id: ProjectID,
    node_id: NodeID,
) -> DynamicServiceStop:
    return TypeAdapter(DynamicServiceStop).validate_python(
        DynamicServiceStop.model_json_schema()["example"]
        | {
            "product_name": product_name,
            "user_id": user_id,
            "project_id": project_id,
            "node_id": f"{node_id}",
        }
    )


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
