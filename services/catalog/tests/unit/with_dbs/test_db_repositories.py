# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import itertools
import random
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterator, List, Tuple

import pytest
from aiopg.sa.engine import Engine
from faker import Faker
from models_library.services import ServiceAccessRightsAtDB, ServiceMetaDataAtDB
from packaging import version
from simcore_postgres_database.models.products import products
from simcore_service_catalog.db.repositories.services import ServicesRepository
from simcore_service_catalog.db.tables import (
    groups,
    services_access_rights,
    services_meta_data,
)
from simcore_service_catalog.utils.versioning import is_patch_release

pytest_simcore_core_services_selection = [
    "postgres",
]
pytest_simcore_ops_services_selection = [
    "adminer",
]


# DATABASE tables used by the catalog-------
#
# services_meta_data       -> groups(gid)@owner
# services_access_rights   -> groups(gid)@owner, products(name)@produt_name, services_meta_data
# services_consume_filetypes
#
# groups
# products
#


@pytest.fixture()
async def products_names(aiopg_engine: Engine) -> Iterator[List[str]]:
    """Inserts products in pg db table and returns its names"""
    data = [
        # already upon creation: ("osparc", r"([\.-]{0,1}osparc[\.-])"),
        ("s4l", r"(^s4l[\.-])|(^sim4life\.)|(^api.s4l[\.-])|(^api.sim4life\.)"),
        ("tis", r"(^tis[\.-])|(^ti-solutions\.)"),
    ]

    # pylint: disable=no-value-for-parameter

    async with aiopg_engine.acquire() as conn:
        # NOTE: The 'default' dialect with current database version settings does not support in-place multirow inserts
        for name, regex in data:
            stmt = products.insert().values(name=name, host_regex=regex)
            await conn.execute(stmt)

    names = [
        "osparc",
    ] + [items[0] for items in data]
    yield names

    async with aiopg_engine.acquire() as conn:
        await conn.execute(products.delete())


@pytest.fixture()
async def user_groups_ids(aiopg_engine: Engine) -> Iterator[List[int]]:
    """Inserts groups in the pg-db table and returns group identifiers"""

    cols = ("gid", "name", "description", "type", "thumbnail", "inclusion_rules")
    data = [
        (34, "john.smith", "primary group for user", "PRIMARY", None, {}),
        (
            20001,
            "Team Black",
            "External testers",
            "STANDARD",
            "http://mib.org",
            {"email": "@(foo|testers|mib)+.(org|com)$"},
        ),
    ]
    # pylint: disable=no-value-for-parameter

    async with aiopg_engine.acquire() as conn:
        for row in data:
            # NOTE: The 'default' dialect with current database version settings does not support in-place multirow inserts
            stmt = groups.insert().values(**dict(zip(cols, row)))
            await conn.execute(stmt)

    gids = [
        1,
    ] + [items[0] for items in data]

    yield gids

    async with aiopg_engine.acquire() as conn:
        await conn.execute(services_meta_data.delete())
        await conn.execute(groups.delete().where(groups.c.gid.in_(gids[1:])))


@pytest.fixture()
async def services_db_tables_injector(aiopg_engine: Engine) -> Callable:
    """Returns a helper to add services in pg db by inserting in
    services_meta_data and services_access_rights tables

    """
    # pylint: disable=no-value-for-parameter

    async def inject_in_db(fake_catalog: List[Tuple]):
        # [(service, ar1, ...), (service2, ar1, ...) ]

        async with aiopg_engine.acquire() as conn:
            # NOTE: The 'default' dialect with current database version settings does not support in-place multirow inserts
            for service in [items[0] for items in fake_catalog]:
                stmt_meta = services_meta_data.insert().values(**service)
                await conn.execute(stmt_meta)

            for access_rights in itertools.chain(items[1:] for items in fake_catalog):
                stmt_access = services_access_rights.insert().values(access_rights)
                await conn.execute(stmt_access)

    yield inject_in_db

    async with aiopg_engine.acquire() as conn:
        await conn.execute(services_access_rights.delete())
        await conn.execute(services_meta_data.delete())


@pytest.fixture()
async def service_catalog_faker(
    user_groups_ids: List[int],
    products_names: List[str],
    faker: Faker,
) -> Callable:
    """Returns a fake factory function with arguments
        service, owner_access, [team_access], [everyone_access]
    that can be used to fill services_meta_data and services_access_rights tables
    """
    everyone_gid, user_gid, team_gid = user_groups_ids

    def _random_service(**overrides) -> Dict[str, Any]:
        data = dict(
            key=f"simcore/services/{random.choice(['dynamic', 'computational'])}/{faker.name()}",
            version=".".join([str(faker.pyint()) for _ in range(3)]),
            owner=user_gid,
            name=faker.name(),
            description=faker.sentence(),
            thumbnail=random.choice([faker.image_url(), None]),
            classifiers=[],
            quality={},
        )
        data.update(overrides)
        return data

    def _random_access(service, **overrides) -> Dict[str, Any]:
        data = dict(
            key=service["key"],
            version=service["version"],
            gid=random.choice(user_groups_ids),
            execute_access=faker.pybool(),
            write_access=faker.pybool(),
            product_name=random.choice(products_names),
        )
        data.update(overrides)
        return data

    def _create_fakes(
        key, version, team_access=None, everyone_access=None, product=products_names[0]
    ) -> Tuple[Dict[str, Any], ...]:

        service = _random_service(key=key, version=version)

        # owner always has full-access
        owner_access = _random_access(
            service,
            gid=service["owner"],
            execute_access=True,
            write_access=True,
            product_name=product,
        )

        fakes = [
            service,
            owner_access,
        ]
        if team_access:
            fakes.append(
                _random_access(
                    service,
                    gid=team_gid,
                    execute_access="x" in team_access,
                    write_access="w" in team_access,
                    product_name=product,
                )
            )
        if everyone_access:
            fakes.append(
                _random_access(
                    service,
                    gid=everyone_gid,
                    execute_access="x" in everyone_access,
                    write_access="w" in everyone_access,
                    product_name=product,
                )
            )
        return tuple(fakes)

    return _create_fakes


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


async def test_copy_access_rights_from_previous_release(
    fake_catalog_with_jupyterlab: FakeCatalogInfo,
    services_repo: ServicesRepository,
):
    releases = await services_repo.list_service_releases(
        "simcore/services/dynamic/jupyterlab", limit_count=2, major=1, minor=1
    )
    assert len(releases) == 2
    latest_release, previous_patch = releases

    # get all access-rights set for previous_patch (for all products!!!)
    access_rights: List[
        ServiceAccessRightsAtDB
    ] = await services_repo.get_service_access_rights(
        **previous_patch.dict(include={"key", "version"})
    )

    # copy them over to latest-release.
    #
    # Notice that if latest-release had already access-rights
    # those get overriden or ADD new access-rights.
    #
    for access in access_rights:
        access.version = latest_release.version
    await services_repo.upsert_service_access_rights(access_rights)


@pytest.mark.skip(reason="dev")
def test_it(services_catalog):

    # service S has a new patch released: 1.2.5 (i.e. backwards compatible bug fix, according to semver policies )
    current_version = "1.10.5"
    new_version = "1.10.6"

    # the owner of service, checked the auto-upgrade patch policy in the publication contract (i.e.metadata.yml)

    # service S:1.2.5 gets automatically the same access rights as S:1.2.4.
    # access_rights = get_access_rights(service_key, service_version)

    # set_access_rights(service_key, service_version, access_rights)

    # NO
    # all projects with nodes assigned to S:1.2.X get promoted to the latest patch S:1.2.5

    # services can be published on different products (including file-picker and group nodes)
