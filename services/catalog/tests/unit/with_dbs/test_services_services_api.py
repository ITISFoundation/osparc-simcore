# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from collections.abc import Callable
from typing import Any

import pytest
from fastapi import FastAPI
from models_library.products import ProductName
from models_library.users import UserID
from respx.router import MockRouter
from simcore_service_catalog.api.dependencies.director import get_director_api
from simcore_service_catalog.db.repositories.services import ServicesRepository
from simcore_service_catalog.services import manifest, services_api
from simcore_service_catalog.services.director import DirectorApi
from sqlalchemy.ext.asyncio import AsyncEngine

pytest_simcore_core_services_selection = [
    "postgres",
]
pytest_simcore_ops_services_selection = [
    "adminer",
]


@pytest.fixture
def services_repo(sqlalchemy_async_engine: AsyncEngine):
    return ServicesRepository(sqlalchemy_async_engine)


@pytest.fixture
def num_services() -> int:
    return 5


@pytest.fixture
def num_versions_per_service() -> int:
    return 20


@pytest.fixture
def fake_services_data(
    target_product: ProductName,
    create_fake_service_data: Callable,
    num_services: int,
    num_versions_per_service: int,
) -> list:
    return [
        create_fake_service_data(
            f"simcore/services/comp/some-service-{n}",
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
    fake_services_data: list,
    create_director_list_services_from: Callable,
) -> list[dict[str, Any]]:
    # OVERRIDES: Changes the values returned by the mocked_director_service_api

    return create_director_list_services_from(
        expected_director_list_services, fake_services_data
    )


@pytest.fixture
async def background_sync_task_mocked(
    background_tasks_setup_disabled: None,
    services_db_tables_injector: Callable,
    fake_services_data: list,
) -> None:
    # inject db services (typically done by the sync background task)
    await services_db_tables_injector(fake_services_data)


@pytest.fixture
async def director_client(app: FastAPI) -> DirectorApi:
    director_api = get_director_api(app)

    # ensures manifest API cache is reset
    assert hasattr(manifest.get_service, "cache")
    assert await manifest.get_service.cache.clear()

    return director_api


async def test_list_services_paginated(
    background_sync_task_mocked: None,
    rabbitmq_and_rpc_setup_disabled: None,
    mocked_director_service_api: MockRouter,
    target_product: ProductName,
    services_repo: ServicesRepository,
    user_id: UserID,
    director_client: DirectorApi,
    num_services: int,
):

    offset = 1
    limit = 2
    assert limit < num_services

    assert not mocked_director_service_api["get_service"].called

    total_count, page_items = await services_api.list_services_paginated(
        services_repo,
        director_client,
        product_name=target_product,
        user_id=user_id,
        limit=limit,
        offset=offset,
    )

    assert total_count == num_services
    assert page_items
    assert len(page_items) <= limit
    assert mocked_director_service_api["get_service"].called
    assert mocked_director_service_api["get_service"].call_count == limit

    for item in page_items:
        assert item.access_rights
        assert item.owner is not None
        assert item.history[0].version == item.version

        got = await services_api.get_service(
            services_repo,
            director_client,
            product_name=target_product,
            user_id=user_id,
            service_key=item.key,
            service_version=item.version,
        )

        assert got == item

    # since it is cached, it should only call it `limit` times
    assert mocked_director_service_api["get_service"].call_count == limit


async def test_batch_get_my_services(
    background_sync_task_mocked: None,
    rabbitmq_and_rpc_setup_disabled: None,
    mocked_director_service_api: MockRouter,
    target_product: ProductName,
    services_repo: ServicesRepository,
    user_id: UserID,
    director_client: DirectorApi,
    create_fake_service_data: Callable,
    services_db_tables_injector: Callable,
):
    # Create fake services data
    service_key = "simcore/services/comp/some-service"
    service_version_1 = "1.0.0"
    service_version_2 = "2.0.0"
    other_service_key = "simcore/services/comp/other-service"
    other_service_version = "1.0.0"

    fake_service_1 = create_fake_service_data(
        service_key,
        service_version_1,
        team_access=None,
        everyone_access=None,
        product=target_product,
    )
    fake_service_2 = create_fake_service_data(
        service_key,
        service_version_2,
        team_access="x",
        everyone_access=None,
        product=target_product,
    )
    fake_service_3 = create_fake_service_data(
        other_service_key,
        other_service_version,
        team_access=None,
        everyone_access=None,
        product=target_product,
    )

    # Inject fake services into the database
    await services_db_tables_injector([fake_service_1, fake_service_2, fake_service_3])

    # Batch get my services
    ids = [
        (service_key, service_version_1),
        (service_key, service_version_2),
        (other_service_key, other_service_version),
    ]

    my_services = await services_api.batch_get_my_services(
        repo=services_repo,
        product_name=target_product,
        user_id=user_id,
        ids=ids,
    )

    assert len(my_services) == 3

    # Check access rights
    assert my_services[0].my_access_rights == {}
    assert my_services[1].my_access_rights is not None
    assert my_services[2].my_access_rights is not None
    assert my_services[2].owner is not None
