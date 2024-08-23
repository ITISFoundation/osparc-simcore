# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from collections.abc import Callable
from dataclasses import dataclass, field

import pytest
from models_library.products import ProductName
from models_library.users import UserID
from packaging import version
from packaging.version import Version
from pydantic import EmailStr, parse_obj_as
from simcore_service_catalog.db.repositories.services import ServicesRepository
from simcore_service_catalog.models.services_db import (
    ServiceAccessRightsAtDB,
    ServiceMetaDataAtDB,
)
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
    service = ServiceMetaDataAtDB.parse_obj(fake_service)
    service_access_rights = [
        ServiceAccessRightsAtDB.parse_obj(a) for a in fake_access_rights
    ]

    new_service = await services_repo.create_or_update_service(
        service, service_access_rights
    )

    assert new_service.dict(include=set(fake_service.keys())) == service.dict()


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
        product_name=target_product, **service.dict(include={"key", "version"})
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
        product_name=target_product, **service.dict(include={"key", "version"})
    )
    assert {user_gid, team_gid} == {a.gid for a in access_rights}


async def test_list_service_releases(
    fake_catalog_with_jupyterlab: FakeCatalogInfo,
    services_repo: ServicesRepository,
):
    services: list[ServiceMetaDataAtDB] = await services_repo.list_service_releases(
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

    releases_1_1_x: list[
        ServiceMetaDataAtDB
    ] = await services_repo.list_service_releases(
        "simcore/services/dynamic/jupyterlab", major=1, minor=1
    )
    assert [
        s.version for s in releases_1_1_x
    ] == fake_catalog_with_jupyterlab.expected_1_1_x

    expected_0_x_x: list[
        ServiceMetaDataAtDB
    ] = await services_repo.list_service_releases(
        "simcore/services/dynamic/jupyterlab", major=0
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

    assert services_items[0].key == "simcore/services/dynamic/jupyterlab"
    history = services_items[0].history
    assert len(history) == fake_catalog_with_jupyterlab.expected_services_count

    # latest, ..., first version
    assert history[0].version == fake_catalog_with_jupyterlab.expected_latest

    # check sorted
    got_versions = [Version(h.version) for h in history]
    assert got_versions == sorted(got_versions, reverse=True)


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
        assert len(service.history) == num_versions_per_service
        assert service.version == expected_latest_version

    _, services_items = await services_repo.list_latest_services(
        product_name=target_product, user_id=user_id, limit=2
    )
    assert len(services_items) == 2

    for service in services_items:
        assert len(service.history) == num_versions_per_service

        assert parse_obj_as(EmailStr, service.owner_email), "resolved own'es email"

        expected_latest_version = service.history[0].version  # latest service is first
        assert service.version == expected_latest_version


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
        ServiceMetaDataAtDB.construct(
            key=service_key, version=service_version, name="foo"
        ),
    )
    updated = await services_repo.get_service(service_key, service_version)

    assert got.copy(update={"name": "foo"}) == updated

    assert await services_repo.get_service(service_key, service_version) == updated


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
