# pylint:disable=redefined-outer-name

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import AsyncExitStack
from typing import Any

import pytest
from models_library.api_schemas_dynamic_scheduler.dynamic_services import DynamicServiceStart, DynamicServiceStop
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.users import UserID
from pydantic import TypeAdapter
from pytest_simcore.helpers.faker_factories import random_product, random_project, random_user
from pytest_simcore.helpers.postgres_tools import (
    insert_and_get_row_lifespan,
)
from simcore_postgres_database.models.products import products
from simcore_postgres_database.models.projects import projects
from simcore_postgres_database.models.users import users
from sqlalchemy.ext.asyncio import AsyncEngine


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
