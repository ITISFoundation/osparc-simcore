# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from collections.abc import Callable

import pytest
from models_library.products import ProductName
from models_library.users import UserID
from simcore_service_catalog.db.repositories.services import ServicesRepository
from simcore_service_catalog.services import catalog
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


async def test_list_services_paginated(
    target_product: ProductName,
    create_fake_service_data: Callable,
    services_db_tables_injector: Callable,
    services_repo: ServicesRepository,
    user_id: UserID,
):
    # inject services
    num_services = 5
    num_versions_per_service = 20
    await services_db_tables_injector(
        [
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
    )

    limit = 2
    assert limit < num_services
    offset = 1

    total_count, page_items = await catalog.list_services_paginated(
        services_repo,
        product_name=target_product,
        user_id=user_id,
        limit=limit,
        offset=offset,
    )

    assert total_count == num_services
    assert len(page_items) <= limit

    for item in page_items:
        assert item.access_rights
        assert item.owner is not None
        assert item.history[0].version == item.version

        got = await catalog.get_service(
            services_repo,
            product_name=target_product,
            user_id=user_id,
            service_key=item.key,
            service_version=item.version,
        )

        assert got == item
