# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from dataclasses import dataclass, field
from typing import Callable, List

import pytest
from models_library.services import ServiceAccessRightsAtDB, ServiceMetaDataAtDB
from packaging import version
from simcore_service_catalog.db.repositories.services import ServicesRepository
from simcore_service_catalog.utils.versioning import is_patch_release

pytest_simcore_core_services_selection = [
    "postgres",
]
pytest_simcore_ops_services_selection = [
    "adminer",
]


@pytest.fixture
def services_repo(aiopg_engine):
    repo = ServicesRepository(aiopg_engine)
    return repo


@dataclass
class FakeCatalogInfo:
    jupyter_service_key: str = "simcore/services/dynamic/jupyterlab"
    expected_services_count: int = 5
    expected_latest: str = "1.1.3"
    expected_1_1_x: List[str] = field(default_factory=list)
    expected_0_x_x: List[str] = field(default_factory=list)


@pytest.fixture()
async def fake_catalog_with_jupyterlab(
    products_names: List[str],
    service_catalog_faker: Callable,
    services_db_tables_injector: Callable,
) -> FakeCatalogInfo:

    target_product = products_names[-1]

    # injects fake data in db
    await services_db_tables_injector(
        [
            service_catalog_faker(
                "simcore/services/dynamic/jupyterlab",
                "0.0.1",
                team_access=None,
                everyone_access=None,
                product=target_product,
            ),
            service_catalog_faker(
                "simcore/services/dynamic/jupyterlab",
                "0.0.7",
                team_access=None,
                everyone_access=None,
                product=target_product,
            ),
            service_catalog_faker(
                "simcore/services/dynamic/jupyterlab",
                "0.10.0",
                team_access="x",
                everyone_access=None,
                product=target_product,
            ),
            service_catalog_faker(
                "simcore/services/dynamic/jupyterlab",
                "1.1.0",
                team_access="xw",
                everyone_access=None,
                product=target_product,
            ),
            service_catalog_faker(
                "simcore/services/dynamic/jupyterlab",
                "1.1.3",
                team_access=None,
                everyone_access=None,
                product=target_product,
            ),
        ]
    )

    info = FakeCatalogInfo(
        expected_services_count=5,
        expected_latest="1.1.3",
        expected_1_1_x=["1.1.3", "1.1.0"],
        expected_0_x_x=["0.10.0", "0.0.7", "0.0.1"],
    )
    return info


# TESTS ----------------


async def test_create_services(
    services_repo: ServicesRepository, service_catalog_faker: Callable
):
    # creates fake data
    fake_service, *fake_access_rights = service_catalog_faker(
        "simcore/services/dynamic/jupyterlab",
        "1.0.0",
        team_access=None,
        everyone_access=None,
    )

    # validation
    service = ServiceMetaDataAtDB.parse_obj(fake_service)
    service_access_rights = [
        ServiceAccessRightsAtDB.parse_obj(a) for a in fake_access_rights
    ]

    new_service = await services_repo.create_service(service, service_access_rights)

    assert new_service.dict(include=set(fake_service.keys())) == service.dict()


async def test_read_services(
    services_repo: ServicesRepository,
    user_groups_ids: List[int],
    products_names: List[str],
    service_catalog_faker: Callable,
    services_db_tables_injector: Callable,
):
    target_product = products_names[-1]

    # injects fake data in db
    await services_db_tables_injector(
        [
            service_catalog_faker(
                "simcore/services/dynamic/jupyterlab",
                "1.0.0",
                team_access=None,
                everyone_access=None,
                product=target_product,
            ),
            service_catalog_faker(
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
    services: List[ServiceMetaDataAtDB] = await services_repo.list_service_releases(
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

    releases_1_1_x: List[
        ServiceMetaDataAtDB
    ] = await services_repo.list_service_releases(
        "simcore/services/dynamic/jupyterlab", major=1, minor=1
    )
    assert [
        s.version for s in releases_1_1_x
    ] == fake_catalog_with_jupyterlab.expected_1_1_x

    expected_0_x_x: List[
        ServiceMetaDataAtDB
    ] = await services_repo.list_service_releases(
        "simcore/services/dynamic/jupyterlab", major=0
    )
    assert [
        s.version for s in expected_0_x_x
    ] == fake_catalog_with_jupyterlab.expected_0_x_x
