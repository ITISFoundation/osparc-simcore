# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import random
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field

import pytest
from models_library.products import ProductName
from models_library.users import UserID
from packaging import version
from pydantic import EmailStr, HttpUrl, TypeAdapter
from simcore_service_catalog.models.services_db import (
    ServiceAccessRightsAtDB,
    ServiceMetaDataDBCreate,
    ServiceMetaDataDBGet,
    ServiceMetaDataDBPatch,
)
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
    create_fake_service_data: Callable,
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
    services_repo: ServicesRepository, create_fake_service_data: Callable
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
        ServiceAccessRightsAtDB.model_validate(a) for a in fake_access_rights
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
    create_fake_service_data: Callable, url_object: str | HttpUrl | None
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
    create_fake_service_data: Callable,
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


async def test_list_all_services_and_history(
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


async def test_listing_with_no_services(
    target_product: ProductName,
    services_repo: ServicesRepository,
    user_id: UserID,
):
    total_count, services_items = await services_repo.list_latest_services(
        product_name=target_product, user_id=user_id
    )
    assert len(services_items) == 0
    assert total_count == 0


async def test_list_all_services_and_history_with_pagination(
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
        product_name=target_product, user_id=user_id, limit=2
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


async def test_get_and_update_service_meta_data(
    target_product: ProductName,
    create_fake_service_data: Callable,
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
    create_fake_service_data: Callable,
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


async def test_get_service_history_page(
    target_product: ProductName,
    create_fake_service_data: Callable,
    services_db_tables_injector: Callable,
    services_repo: ServicesRepository,
    user_id: UserID,
):
    # inject services with multiple versions
    service_key = "simcore/services/dynamic/test-some-service"
    num_versions = 10

    release_versions = [
        f"{random.randint(0, 2)}.{random.randint(0, 9)}.{random.randint(0, 9)}"  # noqa: S311
        for _ in range(num_versions)
    ]
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
        limit=limit,
        offset=offset,
    )
    assert total_count == num_versions
    assert len(paginated_history) == limit
    assert [release.version for release in paginated_history] == release_versions[
        offset : offset + limit
    ]

    # compare paginated results with the corresponding slice of the full history
    assert paginated_history == history[offset : offset + limit]
