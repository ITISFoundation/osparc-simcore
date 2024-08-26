# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from collections.abc import AsyncIterator, Callable
from typing import Any

import pytest
from faker import Faker
from fastapi import FastAPI
from models_library.products import ProductName
from models_library.rest_pagination import MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE
from models_library.services_types import ServiceKey, ServiceVersion
from models_library.users import UserID
from pydantic import ValidationError
from pytest_simcore.helpers.faker_factories import random_user
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.postgres_tools import insert_and_get_row_lifespan
from pytest_simcore.helpers.typing_env import EnvVarsDict
from respx.router import MockRouter
from servicelib.rabbitmq import RabbitMQRPCClient
from servicelib.rabbitmq.rpc_interfaces.catalog.errors import (
    CatalogForbiddenError,
    CatalogItemNotFoundError,
)
from servicelib.rabbitmq.rpc_interfaces.catalog.services import (
    check_for_service,
    get_service,
    list_services_paginated,
    update_service,
)
from simcore_postgres_database.models.users import users
from sqlalchemy.ext.asyncio import AsyncEngine

pytest_simcore_core_services_selection = [
    "rabbit",
    "postgres",
]
pytest_simcore_ops_services_selection = []


@pytest.fixture
def app_environment(
    monkeypatch: pytest.MonkeyPatch,
    app_environment: EnvVarsDict,
    rabbit_env_vars_dict: EnvVarsDict,  # rabbitMQ settings from 'rabbit' service
) -> EnvVarsDict:
    monkeypatch.delenv("CATALOG_RABBITMQ", raising=False)
    return setenvs_from_dict(
        monkeypatch,
        {**app_environment, **rabbit_env_vars_dict},
    )


@pytest.fixture
def num_services() -> int:
    return 5


@pytest.fixture
def num_versions_per_service() -> int:
    return 20


@pytest.fixture
def fake_data_for_services(
    target_product: ProductName,
    create_fake_service_data: Callable,
    num_services: int,
    num_versions_per_service: int,
) -> list:
    return [
        create_fake_service_data(
            f"simcore/services/comp/test-api-rpc-service-{n}",
            f"{v}.0.0",
            team_access=None,
            everyone_access=None,
            product=target_product,
        )
        for n in range(num_services)
        for v in range(num_versions_per_service)
    ]


@pytest.fixture
def expected_director_list_services(
    expected_director_list_services: list[dict[str, Any]],
    fake_data_for_services: list,
    create_director_list_services_from: Callable,
) -> list[dict[str, Any]]:
    # OVERRIDES: Changes the values returned by the mocked_director_service_api

    return create_director_list_services_from(
        expected_director_list_services, fake_data_for_services
    )


@pytest.fixture
async def background_sync_task_mocked(
    background_tasks_setup_disabled: None,
    services_db_tables_injector: Callable,
    fake_data_for_services: list,
) -> None:
    # inject db services (typically done by the sync background task)
    await services_db_tables_injector(fake_data_for_services)


async def test_rpc_catalog_client(
    background_sync_task_mocked: None,
    mocked_director_service_api: MockRouter,
    rpc_client: RabbitMQRPCClient,
    product_name: ProductName,
    user_id: UserID,
    app: FastAPI,
):
    assert app

    page = await list_services_paginated(
        rpc_client, product_name=product_name, user_id=user_id
    )

    assert page.data
    service_key = page.data[0].key
    service_version = page.data[0].version

    with pytest.raises(ValidationError):
        await list_services_paginated(
            rpc_client,
            product_name=product_name,
            user_id=user_id,
            limit=MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE + 1,
        )

    got = await get_service(
        rpc_client,
        product_name=product_name,
        user_id=user_id,
        service_key=service_key,
        service_version=service_version,
    )
    assert got.key == service_key
    assert got.version == service_version

    assert got == next(
        item
        for item in page.data
        if (item.key == service_key and item.version == service_version)
    )

    updated = await update_service(
        rpc_client,
        product_name=product_name,
        user_id=user_id,
        service_key=service_key,
        service_version=service_version,
        update={
            "name": "foo",
            "description": "bar",
            "version_display": "this is a nice version",
        },
    )

    assert updated.key == got.key
    assert updated.version == got.version
    assert updated.name == "foo"
    assert updated.description == "bar"
    assert updated.version_display == "this is a nice version"
    assert not updated.classifiers

    got = await get_service(
        rpc_client,
        product_name=product_name,
        user_id=user_id,
        service_key=service_key,
        service_version=service_version,
    )
    assert got == updated


async def test_rpc_get_service_not_found_error(
    background_sync_task_mocked: None,
    mocked_director_service_api: MockRouter,
    app: FastAPI,
    rpc_client: RabbitMQRPCClient,
    product_name: ProductName,
    user_id: UserID,
):

    with pytest.raises(CatalogItemNotFoundError, match="unknown"):
        await get_service(
            rpc_client,
            product_name=product_name,
            user_id=user_id,
            service_key="simcore/services/dynamic/unknown",
            service_version="1.0.0",
        )


async def test_rpc_get_service_validation_error(
    background_sync_task_mocked: None,
    mocked_director_service_api: MockRouter,
    app: FastAPI,
    rpc_client: RabbitMQRPCClient,
    product_name: ProductName,
    user_id: UserID,
):

    with pytest.raises(ValidationError, match="service_key"):
        await get_service(
            rpc_client,
            product_name=product_name,
            user_id=user_id,
            service_key="wrong-format/unknown",
            service_version="1.0.0",
        )


async def test_rpc_check_for_service(
    background_sync_task_mocked: None,
    mocked_director_service_api: MockRouter,
    app: FastAPI,
    rpc_client: RabbitMQRPCClient,
    product_name: ProductName,
    user_id: UserID,
):
    with pytest.raises(CatalogItemNotFoundError, match="unknown"):
        await check_for_service(
            rpc_client,
            product_name=product_name,
            user_id=user_id,
            service_key="simcore/services/dynamic/unknown",
            service_version="1.0.0",
        )


@pytest.fixture
async def other_user(
    user_id: UserID,
    sqlalchemy_async_engine: AsyncEngine,
    faker: Faker,
) -> AsyncIterator[dict[str, Any]]:

    _user = random_user(fake=faker, id=user_id + 1)
    async with insert_and_get_row_lifespan(
        sqlalchemy_async_engine,
        table=users,
        values=_user,
        pk_col=users.c.id,
        pk_value=_user["id"],
    ) as row:
        yield row


async def test_rpc_get_service_access_rights(
    background_sync_task_mocked: None,
    mocked_director_service_api: MockRouter,
    rpc_client: RabbitMQRPCClient,
    product_name: ProductName,
    user: dict[str, Any],
    user_id: UserID,
    other_user: dict[str, Any],
    app: FastAPI,
    create_fake_service_data: Callable,
    target_product: ProductName,
):
    assert app
    assert user["id"] == user_id

    # user_id owns a service (created in background_sync_task_mocked)
    service_key = ServiceKey("simcore/services/comp/test-api-rpc-service-0")
    service_version = ServiceVersion("0.0.0")

    service = await get_service(
        rpc_client,
        product_name=product_name,
        user_id=user_id,
        service_key=service_key,
        service_version=service_version,
    )
    assert service
    assert service.access_rights
    assert service.access_rights[user["primary_gid"]].write
    assert service.access_rights[user["primary_gid"]].execute

    assert other_user["primary_gid"] not in service.access_rights

    # other_user does not have EXECUTE access -----------------
    with pytest.raises(CatalogForbiddenError, match=service_key):
        await get_service(
            rpc_client,
            product_name=product_name,
            user_id=other_user["id"],
            service_key=service_key,
            service_version=service_version,
        )

    # other_user does not have WRITE access
    with pytest.raises(CatalogForbiddenError, match=service_key):
        await update_service(
            rpc_client,
            product_name=product_name,
            user_id=other_user["id"],
            service_key=service_key,
            service_version=service_version,
            update={
                "name": "foo",
                "description": "bar",
            },
        )

    # user_id gives "x access" to other_user ------------
    assert service.access_rights is not None
    await update_service(
        rpc_client,
        product_name=product_name,
        user_id=user_id,
        service_key=service_key,
        service_version=service_version,
        update={
            "access_rights": {
                **service.access_rights,
                other_user["primary_gid"]: {
                    "execute": True,
                    "write": False,
                },
            }
        },
    )

    # other user can now GET but NOT UPDATE
    await get_service(
        rpc_client,
        product_name=product_name,
        user_id=other_user["id"],
        service_key=service_key,
        service_version=service_version,
    )

    with pytest.raises(CatalogForbiddenError, match=service_key):
        await update_service(
            rpc_client,
            product_name=product_name,
            user_id=other_user["id"],
            service_key=service_key,
            service_version=service_version,
            update={
                "name": "foo",
                "description": "bar",
            },
        )

    # user_id gives "xw access" to other_user ------------------
    assert service.access_rights is not None
    await update_service(
        rpc_client,
        product_name=product_name,
        user_id=user_id,
        service_key=service_key,
        service_version=service_version,
        update={
            "access_rights": {
                **service.access_rights,
                other_user["primary_gid"]: {
                    "execute": True,
                    "write": True,
                },
            }
        },
    )

    # other_user can now update and get
    await update_service(
        rpc_client,
        product_name=product_name,
        user_id=other_user["id"],
        service_key=service_key,
        service_version=service_version,
        update={
            "name": "foo",
            "description": "bar",
        },
    )
    updated_service = await get_service(
        rpc_client,
        product_name=product_name,
        user_id=other_user["id"],
        service_key=service_key,
        service_version=service_version,
    )
    assert updated_service.dict(include={"name", "description"}) == {
        "name": "foo",
        "description": "bar",
    }
