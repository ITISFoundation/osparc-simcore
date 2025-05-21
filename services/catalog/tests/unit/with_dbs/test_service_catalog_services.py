# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

import pytest
from fastapi import FastAPI
from models_library.api_schemas_catalog.services import MyServiceGet, ServiceSummary
from models_library.products import ProductName
from models_library.users import UserID
from pydantic import TypeAdapter
from pytest_simcore.helpers.catalog_services import CreateFakeServiceDataCallable
from respx.router import MockRouter
from simcore_service_catalog.api._dependencies.director import get_director_client
from simcore_service_catalog.clients.director import DirectorClient
from simcore_service_catalog.repository.groups import GroupsRepository
from simcore_service_catalog.repository.services import ServicesRepository
from simcore_service_catalog.service import catalog_services, manifest
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
def groups_repo(sqlalchemy_async_engine: AsyncEngine):
    return GroupsRepository(sqlalchemy_async_engine)


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
def expected_director_rest_api_list_services(
    expected_director_rest_api_list_services: list[dict[str, Any]],
    fake_services_data: list,
    create_director_list_services_from: Callable,
) -> list[dict[str, Any]]:
    # OVERRIDES: Changes the values returned by the mocked_director_service_api

    return create_director_list_services_from(
        expected_director_rest_api_list_services, fake_services_data
    )


@pytest.fixture
async def background_sync_task_mocked(
    background_task_lifespan_disabled: None,
    services_db_tables_injector: Callable,
    fake_services_data: list,
) -> None:
    """
    Emulates a sync backgroundtask that injects
    some services in the db
    """
    await services_db_tables_injector(fake_services_data)


@pytest.fixture
async def director_client(app: FastAPI) -> DirectorClient:
    director_api = get_director_client(app)

    # ensures manifest API cache is reset
    assert hasattr(manifest.get_service, "cache")
    assert await manifest.get_service.cache.clear()

    return director_api


async def test_list_latest_catalog_services(
    background_sync_task_mocked: None,
    rabbitmq_and_rpc_setup_disabled: None,
    mocked_director_rest_api: MockRouter,
    target_product: ProductName,
    services_repo: ServicesRepository,
    user_id: UserID,
    director_client: DirectorClient,
    num_services: int,
):

    offset = 1
    limit = 2
    assert limit < num_services

    assert not mocked_director_rest_api["get_service"].called

    total_count, page_items = await catalog_services.list_latest_catalog_services(
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
    assert mocked_director_rest_api["get_service"].called
    assert mocked_director_rest_api["get_service"].call_count == limit

    for item in page_items:
        assert item.access_rights
        assert item.owner is not None

        got = await catalog_services.get_catalog_service(
            services_repo,
            director_client,
            product_name=target_product,
            user_id=user_id,
            service_key=item.key,
            service_version=item.version,
        )

        assert got.model_dump(exclude={"history"}) == item.model_dump(
            exclude={"release"}
        )
        assert item.release in got.history

    # since it is cached, it should only call it `limit` times
    assert mocked_director_rest_api["get_service"].call_count == limit


async def test_batch_get_my_services(
    background_task_lifespan_disabled: None,
    rabbitmq_and_rpc_setup_disabled: None,
    mocked_director_rest_api: MockRouter,
    target_product: ProductName,
    services_repo: ServicesRepository,
    groups_repo: GroupsRepository,
    user_id: UserID,
    user: dict[str, Any],
    other_user: dict[str, Any],
    create_fake_service_data: CreateFakeServiceDataCallable,
    services_db_tables_injector: Callable,
):
    # catalog
    service_key = "simcore/services/comp/some-service"
    service_version_1 = "1.0.0"  # can upgrade to 1.0.1
    service_version_2 = "1.0.10"  # latest

    other_service_key = "simcore/services/comp/other-service"
    other_service_version = "2.1.2"

    expected_retirement = datetime.utcnow() + timedelta(
        days=1
    )  # NOTE: old offset-naive column

    # Owned by user
    fake_service_1 = create_fake_service_data(
        service_key,
        service_version_1,
        team_access=None,
        everyone_access=None,
        product=target_product,
        deprecated=expected_retirement,
    )
    fake_service_2 = create_fake_service_data(
        service_key,
        service_version_2,
        team_access="x",
        everyone_access=None,
        product=target_product,
    )

    # Owned by other-user
    fake_service_3 = create_fake_service_data(
        other_service_key,
        other_service_version,
        team_access=None,
        everyone_access=None,
        product=target_product,
    )
    _service, _owner_access = fake_service_3
    _service["owner"] = other_user["primary_gid"]
    _owner_access["gid"] = other_user["primary_gid"]

    # Inject fake services into the database
    await services_db_tables_injector([fake_service_1, fake_service_2, fake_service_3])

    # UNDER TEST -------------------------------

    # Batch get services e.g. services in a project
    services_ids = [
        (service_key, service_version_1),
        (other_service_key, other_service_version),
    ]

    my_services = await catalog_services.batch_get_user_services(
        services_repo,
        groups_repo,
        product_name=target_product,
        user_id=user_id,
        ids=services_ids,
    )

    # CHECKS -------------------------------

    # assert returned order and length as ids
    assert services_ids == [(sc.key, sc.release.version) for sc in my_services]

    assert my_services == TypeAdapter(list[MyServiceGet]).validate_python(
        [
            {
                "key": "simcore/services/comp/some-service",
                "release": {
                    "version": service_version_1,
                    "version_display": None,
                    "released": my_services[0].release.released,
                    "retired": expected_retirement,
                    "compatibility": {
                        "can_update_to": {"version": service_version_2}
                    },  # can be updated
                },
                "owner": user["primary_gid"],
                "my_access_rights": {"execute": True, "write": True},  # full access
            },
            {
                "key": "simcore/services/comp/other-service",
                "release": {
                    "version": other_service_version,
                    "version_display": None,
                    "released": my_services[1].release.released,
                    "retired": None,
                    "compatibility": None,  # cannot be updated
                },
                "owner": other_user["primary_gid"],  # needs to request access
                "my_access_rights": {
                    "execute": False,
                    "write": False,
                },
            },
        ]
    )


async def test_list_all_vs_latest_services(
    background_sync_task_mocked: None,
    rabbitmq_and_rpc_setup_disabled: None,
    mocked_director_rest_api: MockRouter,
    target_product: ProductName,
    services_repo: ServicesRepository,
    user_id: UserID,
    director_client: DirectorClient,
    num_services: int,
    num_versions_per_service: int,
):
    """Test that list_all_catalog_services returns all services as summaries while
    list_latest_catalog_services returns only the latest version of each service with full details.
    """
    # No pagination to get all services
    limit = None
    offset = 0

    # Get latest services first
    latest_total_count, latest_items = (
        await catalog_services.list_latest_catalog_services(
            services_repo,
            director_client,
            product_name=target_product,
            user_id=user_id,
            limit=limit,
            offset=offset,
        )
    )

    # Get all services as summaries
    all_total_count, all_items = await catalog_services.list_all_service_summaries(
        services_repo,
        director_client,
        product_name=target_product,
        user_id=user_id,
        limit=limit,
        offset=offset,
    )

    # Verify counts
    # - latest_total_count should equal num_services since we only get the latest version of each service
    # - all_total_count should equal num_services * num_versions_per_service since we get all versions
    assert latest_total_count == num_services
    assert all_total_count == num_services * num_versions_per_service

    # Verify we got the expected number of items
    assert len(latest_items) == num_services
    assert len(all_items) == num_services * num_versions_per_service

    # Collect all service keys from latest items
    latest_keys = {item.key for item in latest_items}

    # Verify all returned items have the expected structure
    for item in all_items:
        # Each summary should have the basic fields
        assert item.key in latest_keys
        assert item.name
        assert item.description is not None
        assert isinstance(item, ServiceSummary)

    # Group all items by key
    key_to_all_versions = {}
    for item in all_items:
        if item.key not in key_to_all_versions:
            key_to_all_versions[item.key] = []
        key_to_all_versions[item.key].append(item)

    # For each service key, verify we have the expected number of versions
    for key, versions in key_to_all_versions.items():
        assert len(versions) == num_versions_per_service

        # Find this service in latest_items
        latest_item = next(item for item in latest_items if item.key == key)
        # Verify there's a summary item with the same version as the latest
        assert any(item.version == latest_item.version for item in versions)
