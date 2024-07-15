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
from simcore_service_catalog.services import services_api
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


num_services = 5
num_versions_per_service = 20


@pytest.fixture
def fake_services_data(
    target_product: ProductName,
    create_fake_service_data: Callable,
):
    return [
        create_fake_service_data(
            f"simcore/services/dynamic/some-service-{n}",
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
    expected_director_list_services: list[dict[str, Any]], fake_services_data: list
) -> list[dict[str, Any]]:
    expected = []

    return expected


async def test_list_services_paginated(
    background_tasks_setup_disabled: None,
    rabbitmq_and_rpc_setup_disabled: None,
    mocked_director_service_api: MockRouter,
    target_product: ProductName,
    fake_services_data: list,
    services_db_tables_injector: Callable,
    services_repo: ServicesRepository,
    user_id: UserID,
    app: FastAPI,
):
    # inject services
    await services_db_tables_injector(fake_services_data)

    limit = 2
    assert limit < num_services
    offset = 1

    # ----
    director_api = get_director_api(app)

    # ---

    assert not mocked_director_service_api["get_service"].called

    total_count, page_items = await services_api.list_services_paginated(
        services_repo,
        director_api,
        product_name=target_product,
        user_id=user_id,
        limit=limit,
        offset=offset,
    )

    assert total_count == num_services
    assert len(page_items) <= limit
    assert mocked_director_service_api["get_service"].called

    for item in page_items:
        assert item.access_rights
        assert item.owner is not None
        assert item.history[0].version == item.version

        got = await services_api.get_service(
            services_repo,
            director_api,
            product_name=target_product,
            user_id=user_id,
            service_key=item.key,
            service_version=item.version,
        )

        assert got == item
