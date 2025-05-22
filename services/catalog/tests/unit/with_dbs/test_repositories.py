# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import logging
import random
from collections import Counter
from collections.abc import Callable
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from typing import Any

import pytest
from models_library.products import ProductName
from models_library.services_enums import ServiceType  # Import ServiceType enum
from models_library.services_regex import (
    COMPUTATIONAL_SERVICE_KEY_PREFIX,
    DYNAMIC_SERVICE_KEY_PREFIX,
    SERVICE_TYPE_TO_PREFIX_MAP,
)
from models_library.users import UserID
from packaging import version
from pydantic import EmailStr, HttpUrl, TypeAdapter
from pytest_simcore.helpers.catalog_services import CreateFakeServiceDataCallable
from pytest_simcore.helpers.faker_factories import random_project
from pytest_simcore.helpers.postgres_tools import insert_and_get_row_lifespan
from simcore_postgres_database.models.projects import ProjectType, projects
from simcore_service_catalog.models.services_db import (
    ServiceAccessRightsDB,
    ServiceDBFilters,
    ServiceMetaDataDBCreate,
    ServiceMetaDataDBGet,
    ServiceMetaDataDBPatch,
)
from simcore_service_catalog.repository.projects import ProjectsRepository
from simcore_service_catalog.repository.services import ServicesRepository
from simcore_service_catalog.utils.versioning import is_patch_release
from sqlalchemy.ext.asyncio import AsyncEngine

pytest_simcore_core_services_selection = [
    "postgres",
]
pytest_simcore_ops_services_selection = [
    "adminer",
]


@pytest.fixture
def services_repo(sqlalchemy_async_engine: AsyncEngine) -> ServicesRepository:
    return ServicesRepository(sqlalchemy_async_engine)


@pytest.fixture
def projects_repo(sqlalchemy_async_engine: AsyncEngine) -> ProjectsRepository:
    return ProjectsRepository(sqlalchemy_async_engine)


@dataclass
class FakeCatalogInfo:
    jupyter_service_key: str = "simcore/services/dynamic/jupyterlab"
    expected_services_count: int = 5
    expected_latest: str = "1.1.3"
    expected_1_1_x: list[str] = field(default_factory=list)
    expected_0_x_x: list[str] = field(default_factory=list)


@pytest.fixture
async def fake_catalog_with_jupyterlab(
    target_product: ProductName,
    create_fake_service_data: CreateFakeServiceDataCallable,
    services_db_tables_injector: Callable,
) -> FakeCatalogInfo:

    # injects fake data in db
    await services_db_tables_injector(
        [
            create_fake_service_data(
                "simcore/services/dynamic/jupyterlab",
                "0.0.1",
                team_access=None,
                everyone_access=None,
                product=target_product,
            ),
            create_fake_service_data(
                "simcore/services/dynamic/jupyterlab",
                "0.0.7",
                team_access=None,
                everyone_access=None,
                product=target_product,
            ),
            create_fake_service_data(
                "simcore/services/dynamic/jupyterlab",
                "0.10.0",
                team_access="x",
                everyone_access=None,
                product=target_product,
            ),
            create_fake_service_data(
                "simcore/services/dynamic/jupyterlab",
                "1.1.0",
                team_access="xw",
                everyone_access=None,
                product=target_product,
            ),
            create_fake_service_data(
                "simcore/services/dynamic/jupyterlab",
                "1.1.3",
                team_access=None,
                everyone_access=None,
                product=target_product,
            ),
        ]
    )

    return FakeCatalogInfo(
        expected_services_count=5,
        expected_latest="1.1.3",
        expected_1_1_x=["1.1.3", "1.1.0"],
        expected_0_x_x=["0.10.0", "0.0.7", "0.0.1"],
    )


async def test_create_services(
    services_repo: ServicesRepository,
    create_fake_service_data: CreateFakeServiceDataCallable,
):
    # creates fake data
    fake_service, *fake_access_rights = create_fake_service_data(
        "simcore/services/dynamic/jupyterlab",
        "1.0.0",
        team_access="x",
        everyone_access="x",
    )

    # validation
    service_db_create = ServiceMetaDataDBCreate.model_validate(fake_service)
    service_access_rights = [
        ServiceAccessRightsDB.model_validate(a) for a in fake_access_rights
    ]

    new_service = await services_repo.create_or_update_service(
        service_db_create, service_access_rights
    )

    assert new_service.model_dump(
        include=service_db_create.model_fields_set
    ) == service_db_create.model_dump(exclude_unset=True)


@pytest.mark.parametrize(
    "url_object",
    [
        "https://github.com/some/path/to/image.png?raw=true",
        TypeAdapter(HttpUrl).validate_python(
            "https://github.com/some/path/to/image.png?raw=true"
        ),
        "",
        None,
    ],
)
async def test_regression_service_meta_data_db_create(
    create_fake_service_data: CreateFakeServiceDataCallable,
    url_object: str | HttpUrl | None,
):
    fake_service, *_ = create_fake_service_data(
        "simcore/services/dynamic/jupyterlab",
        "1.0.0",
        team_access="x",
        everyone_access="x",
    )

    fake_service["icon"] = url_object
    assert ServiceMetaDataDBCreate.model_validate(fake_service)


async def test_read_services(
    services_repo: ServicesRepository,
    user_groups_ids: list[int],
    target_product: ProductName,
    create_fake_service_data: CreateFakeServiceDataCallable,
    services_db_tables_injector: Callable,
):

    # injects fake data in db
    await services_db_tables_injector(
        [
            create_fake_service_data(
                "simcore/services/dynamic/jupyterlab",
                "1.0.0",
                team_access=None,
                everyone_access=None,
                product=target_product,
            ),
            create_fake_service_data(
                "simcore/services/dynamic/jupyterlab",
                "1.0.2",
                team_access="x",
                everyone_access=None,
                product=target_product,
            ),
        ]
    )

    # list
    services = await services_repo.list_services()
    assert len(services) == 2

    everyone_gid, user_gid, team_gid = user_groups_ids
    assert everyone_gid == 1

    services = await services_repo.list_services(
        gids=[
            user_gid,
        ]
    )
    assert len(services) == 2

    services = await services_repo.list_services(
        gids=[
            team_gid,
        ]
    )
    assert len(services) == 1

    # get 1.0.0
    service = await services_repo.get_service(
        "simcore/services/dynamic/jupyterlab", "1.0.0"
    )
    assert service

    access_rights = await services_repo.get_service_access_rights(
        product_name=target_product, **service.model_dump(include={"key", "version"})
    )
    assert {
        user_gid,
    } == {a.gid for a in access_rights}

    # get patched version
    service = await services_repo.get_service(
        "simcore/services/dynamic/jupyterlab", "1.0.2"
    )
    assert service

    access_rights = await services_repo.get_service_access_rights(
        product_name=target_product, **service.model_dump(include={"key", "version"})
    )
    assert {user_gid, team_gid} == {a.gid for a in access_rights}


async def test_list_service_releases(
    fake_catalog_with_jupyterlab: FakeCatalogInfo,
    services_repo: ServicesRepository,
):
    services: list[ServiceMetaDataDBGet] = await services_repo.list_service_releases(
        "simcore/services/dynamic/jupyterlab"
    )
    assert len(services) == fake_catalog_with_jupyterlab.expected_services_count

    vs = [version.Version(s.version) for s in services]
    assert sorted(vs, reverse=True) == vs

    # list all patches w.r.t latest
    patches = [v for v in vs if is_patch_release("1.1.4", v)]
    assert len(patches) == 2

    # check limit
    releases = await services_repo.list_service_releases(
        "simcore/services/dynamic/jupyterlab", limit_count=2
    )

    assert len(releases) == 2
    last_release, previous_release = releases

    assert is_patch_release(last_release.version, previous_release.version)

    assert last_release == await services_repo.get_latest_release(
        "simcore/services/dynamic/jupyterlab"
    )


async def test_list_service_releases_version_filtered(
    fake_catalog_with_jupyterlab: FakeCatalogInfo,
    services_repo: ServicesRepository,
):
    latest = await services_repo.get_latest_release(
        "simcore/services/dynamic/jupyterlab"
    )
    assert latest
    assert latest.version == fake_catalog_with_jupyterlab.expected_latest

    releases_1_1_x: list[ServiceMetaDataDBGet] = (
        await services_repo.list_service_releases(
            "simcore/services/dynamic/jupyterlab", major=1, minor=1
        )
    )
    assert [
        s.version for s in releases_1_1_x
    ] == fake_catalog_with_jupyterlab.expected_1_1_x

    expected_0_x_x: list[ServiceMetaDataDBGet] = (
        await services_repo.list_service_releases(
            "simcore/services/dynamic/jupyterlab", major=0
        )
    )
    assert [
        s.version for s in expected_0_x_x
    ] == fake_catalog_with_jupyterlab.expected_0_x_x


async def test_get_latest_release(
    services_repo: ServicesRepository, fake_catalog_with_jupyterlab: FakeCatalogInfo
):

    latest = await services_repo.get_latest_release(
        "simcore/services/dynamic/jupyterlab"
    )

    assert latest
    assert latest.version == fake_catalog_with_jupyterlab.expected_latest


async def test_list_latest_services(
    target_product: ProductName,
    user_id: UserID,
    services_repo: ServicesRepository,
    fake_catalog_with_jupyterlab: FakeCatalogInfo,
):

    total_count, services_items = await services_repo.list_latest_services(
        product_name=target_product, user_id=user_id
    )
    assert len(services_items) == 1
    assert total_count == 1

    # latest
    assert services_items[0].key == "simcore/services/dynamic/jupyterlab"
    assert services_items[0].version == fake_catalog_with_jupyterlab.expected_latest

    assert (
        len(services_items[0].history) == 0
    ), "list_latest_service does NOT show history"


async def test_list_latest_services_with_no_services(
    target_product: ProductName,
    services_repo: ServicesRepository,
    user_id: UserID,
):
    total_count, services_items = await services_repo.list_latest_services(
        product_name=target_product, user_id=user_id
    )
    assert len(services_items) == 0
    assert total_count == 0


async def test_list_latest_services_with_pagination(
    target_product: ProductName,
    create_fake_service_data: CreateFakeServiceDataCallable,
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
    expected_latest_version = f"{num_versions_per_service-1}.0.0"

    total_count, services_items = await services_repo.list_latest_services(
        product_name=target_product, user_id=user_id
    )
    assert len(services_items) == num_services
    assert total_count == num_services

    for service in services_items:
        assert len(service.history) == 0, "Do not show history in listing"
        assert service.version == expected_latest_version

    _, services_items = await services_repo.list_latest_services(
        product_name=target_product, user_id=user_id, pagination_limit=2
    )
    assert len(services_items) == 2

    for service in services_items:
        assert len(service.history) == 0, "Do not show history in listing"

        assert TypeAdapter(EmailStr).validate_python(
            service.owner_email
        ), "resolved own'es email"

    duplicates = [
        service_key
        for service_key, count in Counter(
            service.key for service in services_items
        ).items()
        if count > 1
    ]
    assert (
        not duplicates
    ), f"list of latest versions of services cannot have duplicates, found: {duplicates}"


async def test_list_latest_services_with_filters(
    target_product: ProductName,
    create_fake_service_data: CreateFakeServiceDataCallable,
    services_db_tables_injector: Callable,
    services_repo: ServicesRepository,
    user_id: UserID,
):
    # Setup: Inject services with different service types
    await services_db_tables_injector(
        [
            create_fake_service_data(
                f"{DYNAMIC_SERVICE_KEY_PREFIX}/service-name-a-{i}",
                "1.0.0",
                team_access=None,
                everyone_access=None,
                product=target_product,
            )
            for i in range(3)
        ]
        + [
            create_fake_service_data(
                f"{COMPUTATIONAL_SERVICE_KEY_PREFIX}/service-name-b-{i}",
                "1.0.0",
                team_access=None,
                everyone_access=None,
                product=target_product,
            )
            for i in range(2)
        ]
    )

    # Test: Apply filter for ServiceType.DYNAMIC
    filters = ServiceDBFilters(service_type=ServiceType.DYNAMIC)
    total_count, services_items = await services_repo.list_latest_services(
        product_name=target_product, user_id=user_id, filters=filters
    )
    assert total_count == 3
    assert len(services_items) == 3
    assert all(
        service.key.startswith(DYNAMIC_SERVICE_KEY_PREFIX) for service in services_items
    )

    # Test: Apply filter for ServiceType.COMPUTATIONAL
    filters = ServiceDBFilters(service_type=ServiceType.COMPUTATIONAL)
    total_count, services_items = await services_repo.list_latest_services(
        product_name=target_product, user_id=user_id, filters=filters
    )
    assert total_count == 2
    assert len(services_items) == 2
    assert all(
        service.key.startswith(COMPUTATIONAL_SERVICE_KEY_PREFIX)
        for service in services_items
    )


async def test_list_latest_services_with_pattern_filters(
    target_product: ProductName,
    create_fake_service_data: CreateFakeServiceDataCallable,
    services_db_tables_injector: Callable,
    services_repo: ServicesRepository,
    user_id: UserID,
):
    # Setup: Inject services with different patterns
    await services_db_tables_injector(
        [
            create_fake_service_data(
                "simcore/services/dynamic/jupyter-lab",
                "1.0.0",
                team_access=None,
                everyone_access=None,
                product=target_product,
                version_display="2023 Release",
            ),
            create_fake_service_data(
                "simcore/services/dynamic/jupyter-r",
                "1.0.0",
                team_access=None,
                everyone_access=None,
                product=target_product,
                version_display="2024 Beta",
            ),
            create_fake_service_data(
                "simcore/services/dynamic/jupyter-python",
                "1.0.0",
                team_access=None,
                everyone_access=None,
                product=target_product,
            ),
        ]
    )

    # Test: Filter by service key pattern
    filters = ServiceDBFilters(service_key_pattern="*/jupyter-*")
    total_count, services_items = await services_repo.list_latest_services(
        product_name=target_product, user_id=user_id, filters=filters
    )
    assert total_count == 3
    assert len(services_items) == 3
    assert all(
        service.key.endswith("jupyter-lab")
        or service.key.endswith("jupyter-r")
        or service.key.endswith("jupyter-python")
        for service in services_items
    )

    # Test: More specific pattern
    filters = ServiceDBFilters(service_key_pattern="*/jupyter-l*")
    total_count, services_items = await services_repo.list_latest_services(
        product_name=target_product, user_id=user_id, filters=filters
    )
    assert total_count == 1
    assert len(services_items) == 1
    assert services_items[0].key.endswith("jupyter-lab")

    # Test: Filter by version display pattern
    filters = ServiceDBFilters(version_display_pattern="*2023*")
    total_count, services_items = await services_repo.list_latest_services(
        product_name=target_product, user_id=user_id, filters=filters
    )
    assert total_count == 1
    assert len(services_items) == 1
    assert services_items[0].version_display == "2023 Release"

    # Test: Filter by version display pattern with NULL handling
    filters = ServiceDBFilters(version_display_pattern="*")
    total_count, services_items = await services_repo.list_latest_services(
        product_name=target_product, user_id=user_id, filters=filters
    )
    assert total_count == 3  # Should match all, including NULL version_display
    assert len(services_items) == 3

    # Test: Combined filters
    filters = ServiceDBFilters(
        service_key_pattern="*/jupyter-*", version_display_pattern="*2024*"
    )
    total_count, services_items = await services_repo.list_latest_services(
        product_name=target_product, user_id=user_id, filters=filters
    )
    assert total_count == 1
    assert len(services_items) == 1
    assert services_items[0].version_display == "2024 Beta"
    assert services_items[0].key.endswith("jupyter-r")


async def test_get_and_update_service_meta_data(
    target_product: ProductName,
    create_fake_service_data: CreateFakeServiceDataCallable,
    services_db_tables_injector: Callable,
    services_repo: ServicesRepository,
    user_id: UserID,
):

    # inject service
    service_key = "simcore/services/dynamic/some-service"
    service_version = "1.2.3"
    await services_db_tables_injector(
        [
            create_fake_service_data(
                service_key,
                service_version,
                team_access=None,
                everyone_access=None,
                product=target_product,
            )
        ]
    )

    got = await services_repo.get_service(service_key, service_version)
    assert got is not None
    assert got.key == service_key
    assert got.version == service_version

    await services_repo.update_service(
        service_key,
        service_version,
        ServiceMetaDataDBPatch(name="foo"),
    )
    updated = await services_repo.get_service(service_key, service_version)
    assert updated

    expected = got.model_copy(update={"name": "foo", "modified": updated.modified})
    assert updated == expected


async def test_can_get_service(
    target_product: ProductName,
    create_fake_service_data: CreateFakeServiceDataCallable,
    services_db_tables_injector: Callable,
    services_repo: ServicesRepository,
    user_id: UserID,
):

    # inject service
    service_key = "simcore/services/dynamic/some-service"
    service_version = "1.2.3"
    await services_db_tables_injector(
        [
            create_fake_service_data(
                service_key,
                service_version,
                team_access=None,
                everyone_access=None,
                product=target_product,
            )
        ]
    )

    # have access
    assert await services_repo.can_get_service(
        product_name=target_product,
        user_id=user_id,
        key=service_key,
        version=service_version,
    )

    # not found
    assert not await services_repo.can_get_service(
        product_name=target_product,
        user_id=user_id,
        key=service_key,
        version="0.1.0",
    )

    # has no access
    assert not await services_repo.can_get_service(
        product_name=target_product,
        user_id=5,  # OTHER user
        key=service_key,
        version=service_version,
    )


def _create_fake_release_versions(num_versions: int) -> set[str]:
    release_versions = set()
    while len(release_versions) < num_versions:
        release_versions.add(
            f"{random.randint(0, 2)}.{random.randint(0, 9)}.{random.randint(0, 9)}"  # noqa: S311
        )
    return release_versions


async def test_get_service_history_page(
    target_product: ProductName,
    create_fake_service_data: CreateFakeServiceDataCallable,
    services_db_tables_injector: Callable,
    services_repo: ServicesRepository,
    user_id: UserID,
):
    # inject services with multiple versions
    service_key = "simcore/services/dynamic/test-some-service"
    num_versions = 10

    release_versions = _create_fake_release_versions(num_versions)
    await services_db_tables_injector(
        [
            create_fake_service_data(
                service_key,
                service_version,
                team_access=None,
                everyone_access=None,
                product=target_product,
            )
            for service_version in release_versions
        ]
    )
    # sorted AFTER injecting
    release_versions = sorted(release_versions, key=version.Version, reverse=True)

    assert version.Version(release_versions[0]) > version.Version(release_versions[-1])

    # fetch full history using get_service_history_page
    total_count, history = await services_repo.get_service_history_page(
        product_name=target_product,
        user_id=user_id,
        key=service_key,
    )
    assert total_count == num_versions
    assert len(history) == num_versions
    assert [release.version for release in history] == release_versions

    # fetch full history using deprecated get_service_history
    deprecated_history = await services_repo.get_service_history(
        product_name=target_product,
        user_id=user_id,
        key=service_key,
    )
    assert len(deprecated_history) == len(history)
    assert [release.version for release in deprecated_history] == [
        release.version for release in history
    ]

    # fetch paginated history
    limit = 3
    offset = 2
    total_count, paginated_history = await services_repo.get_service_history_page(
        product_name=target_product,
        user_id=user_id,
        key=service_key,
        pagination_limit=limit,
        pagination_offset=offset,
    )
    assert total_count == num_versions
    assert len(paginated_history) == limit
    assert [release.version for release in paginated_history] == release_versions[
        offset : offset + limit
    ]

    # compare paginated results with the corresponding slice of the full history
    assert paginated_history == history[offset : offset + limit]


@pytest.mark.parametrize(
    "expected_service_type,service_prefix", SERVICE_TYPE_TO_PREFIX_MAP.items()
)
async def test_get_service_history_page_with_filters(
    target_product: ProductName,
    create_fake_service_data: CreateFakeServiceDataCallable,
    services_db_tables_injector: Callable,
    services_repo: ServicesRepository,
    user_id: UserID,
    expected_service_type: ServiceType,
    service_prefix: str,
):
    # Setup: Inject services with multiple versions and types
    service_key = f"{service_prefix}/test-service"
    num_versions = 10

    release_versions = _create_fake_release_versions(num_versions)

    await services_db_tables_injector(
        [
            create_fake_service_data(
                service_key,
                service_version,
                team_access=None,
                everyone_access=None,
                product=target_product,
            )
            for _, service_version in enumerate(release_versions)
        ]
    )
    # Sort versions after injecting
    release_versions = sorted(release_versions, key=version.Version, reverse=True)

    # Test: Fetch full history with no filters
    total_count, history = await services_repo.get_service_history_page(
        product_name=target_product,
        user_id=user_id,
        key=service_key,
    )
    assert total_count == num_versions
    assert len(history) == num_versions
    assert [release.version for release in history] == release_versions

    # Test: Apply filter for
    filters = ServiceDBFilters(service_type=expected_service_type)
    total_count, filtered_history = await services_repo.get_service_history_page(
        product_name=target_product,
        user_id=user_id,
        key=service_key,
        filters=filters,
    )
    assert total_count == num_versions
    assert len(filtered_history) == num_versions
    assert [release.version for release in filtered_history] == release_versions

    # Final check: filter by a different service type expecting no results
    different_service_type = (
        ServiceType.COMPUTATIONAL
        if expected_service_type != ServiceType.COMPUTATIONAL
        else ServiceType.DYNAMIC
    )
    filters = ServiceDBFilters(service_type=different_service_type)
    total_count, no_history = await services_repo.get_service_history_page(
        product_name=target_product,
        user_id=user_id,
        key=service_key,
        filters=filters,
    )
    assert total_count == 0
    assert no_history == []


async def test_list_services_from_published_templates(
    user: dict[str, Any],
    projects_repo: ProjectsRepository,
    sqlalchemy_async_engine: AsyncEngine,
):
    # Setup: Use AsyncExitStack to manage multiple insert_and_get_row_lifespan
    async with AsyncExitStack() as stack:
        await stack.enter_async_context(
            insert_and_get_row_lifespan(
                sqlalchemy_async_engine,
                table=projects,
                values=random_project(
                    uuid="template-1",
                    type=ProjectType.TEMPLATE,
                    published=True,
                    prj_owner=user["id"],
                    workbench={
                        "node-1": {
                            "key": "simcore/services/dynamic/jupyterlab",
                            "version": "1.0.0",
                        },
                        "node-2": {
                            "key": "simcore/services/frontend/file-picker",
                            "version": "1.0.0",
                        },
                    },
                ),
                pk_col=projects.c.uuid,
                pk_value="template-1",
            )
        )
        await stack.enter_async_context(
            insert_and_get_row_lifespan(
                sqlalchemy_async_engine,
                table=projects,
                values=random_project(
                    uuid="template-2",
                    type=ProjectType.TEMPLATE,
                    published=False,
                    prj_owner=user["id"],
                    workbench={
                        "node-1": {
                            "key": "simcore/services/dynamic/some-service",
                            "version": "2.0.0",
                        },
                    },
                ),
                pk_col=projects.c.uuid,
                pk_value="template-2",
            )
        )

        # Act: Call the method
        services = await projects_repo.list_services_from_published_templates()

        # Assert: Validate the results
        assert len(services) == 1
        assert services[0].key == "simcore/services/dynamic/jupyterlab"
        assert services[0].version == "1.0.0"


async def test_list_services_from_published_templates_with_invalid_service(
    user: dict[str, Any],
    projects_repo: ProjectsRepository,
    sqlalchemy_async_engine: AsyncEngine,
    caplog,
):
    # Setup: Use AsyncExitStack to manage insert_and_get_row_lifespan
    async with AsyncExitStack() as stack:
        await stack.enter_async_context(
            insert_and_get_row_lifespan(
                sqlalchemy_async_engine,
                table=projects,
                values=random_project(
                    uuid="template-1",
                    type=ProjectType.TEMPLATE,
                    published=True,
                    prj_owner=user["id"],
                    workbench={
                        "node-1": {
                            "key": "simcore/services/frontend/file-picker",
                            "version": "1.0.0",
                        },
                        "node-2": {
                            "key": "simcore/services/dynamic/invalid-service",
                            "version": "invalid",
                        },
                    },
                ),
                pk_col=projects.c.uuid,
                pk_value="template-1",
            )
        )

        # Act: Call the method and capture logs
        with caplog.at_level(logging.WARNING):
            services = await projects_repo.list_services_from_published_templates()

        # Assert: Validate the results
        assert len(services) == 0  # No valid services should be returned
        assert (
            "service {'key': 'simcore/services/dynamic/invalid-service', 'version': 'invalid'} could not be validated"
            in caplog.text
        )


async def test_compare_list_all_and_latest_services(
    target_product: ProductName,
    create_fake_service_data: CreateFakeServiceDataCallable,
    services_db_tables_injector: Callable,
    services_repo: ServicesRepository,
    user_id: UserID,
):
    # Setup: Create multiple versions of the same service and a few distinct services
    service_data: list[tuple] = []

    # Service 1 with multiple versions
    service_key_1 = "simcore/services/dynamic/multi-version"
    service_versions_1 = ["1.0.0", "1.1.0", "2.0.0"]
    service_data.extend(
        [
            create_fake_service_data(
                service_key_1,
                version_,
                team_access=None,
                everyone_access=None,
                product=target_product,
            )
            for version_ in service_versions_1
        ]
    )

    # Service 2 with single version
    service_key_2 = "simcore/services/dynamic/single-version"
    service_data.append(
        create_fake_service_data(
            service_key_2,
            "1.0.0",
            team_access=None,
            everyone_access=None,
            product=target_product,
        )
    )

    # Service 3 with computational type
    service_key_3 = "simcore/services/comp/computational-service"
    service_versions_3 = ["0.5.0", "1.0.0"]
    service_data.extend(
        [
            create_fake_service_data(
                service_key_3,
                version_,
                team_access=None,
                everyone_access=None,
                product=target_product,
            )
            for version_ in service_versions_3
        ]
    )

    await services_db_tables_injector(service_data)

    # Test 1: Compare all services vs latest without filters
    total_all, all_services = await services_repo.list_all_services(
        product_name=target_product, user_id=user_id
    )
    total_latest, latest_services = await services_repo.list_latest_services(
        product_name=target_product, user_id=user_id
    )

    # Verify counts
    # All services should be 6 (3 versions of service 1, 1 of service 2, 2 of service 3)
    assert total_all == 6
    # Latest services should be 3 (one latest for each distinct service key)
    assert total_latest == 3

    # Verify latest services are contained in all services
    latest_key_versions = {(s.key, s.version) for s in latest_services}
    all_key_versions = {(s.key, s.version) for s in all_services}
    assert latest_key_versions.issubset(all_key_versions)

    # Verify latest versions are correct
    latest_versions_by_key = {s.key: s.version for s in latest_services}
    assert latest_versions_by_key[service_key_1] == "2.0.0"
    assert latest_versions_by_key[service_key_2] == "1.0.0"
    assert latest_versions_by_key[service_key_3] == "1.0.0"

    # Test 2: Using service_type filter to get only dynamic services
    filters = ServiceDBFilters(service_type=ServiceType.DYNAMIC)

    total_all_filtered, all_services_filtered = await services_repo.list_all_services(
        product_name=target_product, user_id=user_id, filters=filters
    )
    total_latest_filtered, latest_services_filtered = (
        await services_repo.list_latest_services(
            product_name=target_product, user_id=user_id, filters=filters
        )
    )

    # Verify counts with filter
    assert total_all_filtered == 4  # 3 versions of service 1, 1 of service 2
    assert total_latest_filtered == 2  # 1 latest each for service 1 and 2

    # Verify service types are correct after filtering
    assert all(
        s.key.startswith(DYNAMIC_SERVICE_KEY_PREFIX) for s in all_services_filtered
    )
    assert all(
        s.key.startswith(DYNAMIC_SERVICE_KEY_PREFIX) for s in latest_services_filtered
    )

    # Verify latest versions are correct
    latest_versions_by_key = {s.key: s.version for s in latest_services_filtered}
    assert latest_versions_by_key[service_key_1] == "2.0.0"
    assert latest_versions_by_key[service_key_2] == "1.0.0"
    assert service_key_3 not in latest_versions_by_key  # Filtered out

    # Test 3: Using service_key_pattern to find specific service
    filters = ServiceDBFilters(service_key_pattern="*/multi-*")

    total_all_filtered, all_services_filtered = await services_repo.list_all_services(
        product_name=target_product, user_id=user_id, filters=filters
    )
    total_latest_filtered, latest_services_filtered = (
        await services_repo.list_latest_services(
            product_name=target_product, user_id=user_id, filters=filters
        )
    )

    # Verify counts with key pattern filter
    assert total_all_filtered == 3  # All 3 versions of service 1
    assert total_latest_filtered == 1  # Only latest version of service 1

    # Verify service key pattern is matched
    assert all(s.key == service_key_1 for s in all_services_filtered)
    assert all(s.key == service_key_1 for s in latest_services_filtered)

    # Test 4: Pagination
    # Get first page (limit=2)
    total_all_page1, all_services_page1 = await services_repo.list_all_services(
        product_name=target_product,
        user_id=user_id,
        pagination_limit=2,
        pagination_offset=0,
    )

    # Get second page (limit=2, offset=2)
    total_all_page2, all_services_page2 = await services_repo.list_all_services(
        product_name=target_product,
        user_id=user_id,
        pagination_limit=2,
        pagination_offset=2,
    )

    # Verify pagination
    assert total_all_page1 == 6  # Total count should still be total
    assert total_all_page2 == 6
    assert len(all_services_page1) == 2  # But only 2 items on first page
    assert len(all_services_page2) == 2  # And 2 items on second page

    # Ensure pages have different items
    page1_key_versions = {(s.key, s.version) for s in all_services_page1}
    page2_key_versions = {(s.key, s.version) for s in all_services_page2}
    assert not page1_key_versions.intersection(page2_key_versions)


async def test_list_all_services_empty_database(
    target_product: ProductName,
    services_repo: ServicesRepository,
    user_id: UserID,
):
    """Test list_all_services and list_latest_services with an empty database."""
    # Test with empty database
    total_all, all_services = await services_repo.list_all_services(
        product_name=target_product, user_id=user_id
    )
    total_latest, latest_services = await services_repo.list_latest_services(
        product_name=target_product, user_id=user_id
    )

    assert total_all == 0
    assert len(all_services) == 0
    assert total_latest == 0
    assert len(latest_services) == 0


async def test_list_all_services_deprecated_versions(
    target_product: ProductName,
    create_fake_service_data: CreateFakeServiceDataCallable,
    services_db_tables_injector: Callable,
    services_repo: ServicesRepository,
    user_id: UserID,
):
    """Test that list_all_services includes deprecated versions while list_latest_services ignores them."""
    from datetime import datetime, timedelta

    # Create a service with regular and deprecated versions
    service_key = "simcore/services/dynamic/with-deprecated"
    service_data = []

    # Add regular version
    service_data.append(
        create_fake_service_data(
            service_key,
            "1.0.0",
            team_access=None,
            everyone_access=None,
            product=target_product,
        )
    )

    # Add deprecated version (with higher version number)
    deprecated_service = create_fake_service_data(
        service_key,
        "2.0.0",
        team_access=None,
        everyone_access=None,
        product=target_product,
    )
    # Set deprecated timestamp to yesterday
    deprecated_service[0]["deprecated"] = datetime.now() - timedelta(days=1)
    service_data.append(deprecated_service)

    # Add newer non-deprecated version
    service_data.append(
        create_fake_service_data(
            service_key,
            "3.0.0",
            team_access=None,
            everyone_access=None,
            product=target_product,
        )
    )

    await services_db_tables_injector(service_data)

    # Get all services - should include both deprecated and non-deprecated
    total_all, all_services = await services_repo.list_all_services(
        product_name=target_product, user_id=user_id
    )

    # Get latest services - should only show latest non-deprecated
    total_latest, latest_services = await services_repo.list_latest_services(
        product_name=target_product, user_id=user_id
    )

    # Verify counts
    assert total_all == 3  # All 3 versions

    # Verify latest is the newest non-deprecated version
    assert len(latest_services) == 1
    assert latest_services[0].key == service_key
    assert latest_services[0].version == "3.0.0"

    # Get versions from all services
    versions = [s.version for s in all_services if s.key == service_key]
    assert sorted(versions) == ["1.0.0", "2.0.0", "3.0.0"]

    # Verify the deprecated status is correctly set
    for service in all_services:
        if service.key == service_key and service.version == "2.0.0":
            assert service.deprecated is not None
        else:
            assert service.deprecated is None
