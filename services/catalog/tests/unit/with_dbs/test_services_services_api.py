# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import itertools
from collections.abc import Callable
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from models_library.products import ProductName
from models_library.services_metadata_published import ServiceMetaDataPublished
from models_library.users import UserID
from pydantic import Extra
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
    expected_director_list_services: list[dict[str, Any]], fake_data_for_services: list
) -> list[dict[str, Any]]:
    # OVERRIDES: Changes the values returned by the director API by

    class _Loader(ServiceMetaDataPublished):
        class Config:
            extra = Extra.ignore
            allow_population_by_field_name = True

    return [
        jsonable_encoder(
            _Loader.parse_obj(
                {
                    **next(itertools.cycle(expected_director_list_services)),
                    **service_and_access_rights_data[0],  # service, **access_rights
                }
            ),
            exclude_unset=True,
        )
        for service_and_access_rights_data in fake_data_for_services
    ]


@pytest.fixture
async def background_tasks_setup_disabled(
    background_tasks_setup_disabled: None,
    services_db_tables_injector: Callable,
    fake_data_for_services: list,
) -> None:
    # inject db services (typically done by the sync background task)
    await services_db_tables_injector(fake_data_for_services)


async def test_list_services_paginated(
    background_tasks_setup_disabled: None,
    rabbitmq_and_rpc_setup_disabled: None,
    mocked_director_service_api: MockRouter,
    target_product: ProductName,
    services_repo: ServicesRepository,
    user_id: UserID,
    app: FastAPI,
    num_services: int,
):
    director_api = get_director_api(app)

    offset = 1
    limit = 2
    assert limit < num_services

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
            director_api,
            product_name=target_product,
            user_id=user_id,
            service_key=item.key,
            service_version=item.version,
        )

        assert got == item

    # since it is cached, it should only call it `limit` times
    assert mocked_director_service_api["get_service"].call_count == limit
