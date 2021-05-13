# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import itertools
import random
from typing import Any, Callable, Dict, List, Tuple

import pytest
from aiopg.sa.engine import Engine
from faker import Faker
from models_library.services import (
    ServiceAccessRightsAtDB,
    ServiceGroupAccessRights,
    ServiceMetaDataAtDB,
)
from simcore_postgres_database.models.products import products
from simcore_service_catalog.db.repositories.services import ServicesRepository
from simcore_service_catalog.db.tables import (
    groups,
    services_access_rights,
    services_meta_data,
)

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
async def products_names(aiopg_engine: Engine) -> List[str]:
    """ products created in postgres db """
    data = [
        ("osparc", r"([\.-]{0,1}osparc[\.-])"),
        ("s4l", r"(^s4l[\.-])|(^sim4life\.)|(^api.s4l[\.-])|(^api.sim4life\.)"),
        ("tis", r"(^tis[\.-])|(^ti-solutions\.)"),
    ]
    # pylint: disable=no-value-for-parameter
    stmt = products.insert().values([{"name": n, "host_regex": r} for n, r in data])

    async with aiopg_engine.acquire() as conn:
        await conn.execute(stmt)

    yield [items[0] for items in data]

    async with aiopg_engine.acquire() as conn:
        await conn.execute(products.delete())


@pytest.fixture()
async def user_groups_ids(aiopg_engine: Engine) -> List[int]:
    cols = ("gid", "name", "description", "type", "thumbnail", "inclusion_rules")

    data = [
        (1, "Everyone", "all users", "EVERYONE", None, {}),
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

    stmt = groups.insert().values([dict(zip(cols, row)) for row in data])

    async with aiopg_engine.acquire() as conn:
        await conn.execute(stmt)

    yield [items[0] for items in data]

    async with aiopg_engine.acquire() as conn:
        await conn.execute(groups.delete())


@pytest.fixture()
async def service_catalog_faker(
    user_groups_ids: List[int],
    products_names: List[str],
    faker: Faker,
) -> Callable:
    """Returns a fake factory fo data as
        ( service, owner_access, [team_access], [everyone_access] )

    that can be used to fill services_meta_data and services_access_rights tables
    """
    everyone_gid, user_gid, team_gid = user_groups_ids

    def _create_random_service(**overrides) -> Dict[str, Any]:
        data = dict(
            key=f"simcore/services/{random.choice(['dynamic', 'computational'])}/{faker.name()}",
            version=".".join([faker.pyint() for _ in range(3)]),
            owner=user_gid,
            name=faker.name(),
            description=faker.sentence(),
            thumbnail=random.choice([faker.image_url(), None]),
            classifiers=[],
            quality={},
        )
        data.update(overrides)
        return data

    def _create_random_access(service, **overrides) -> Dict[str, Any]:
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

    def _create_fake(
        key, version, team_access=None, everyone_access=None
    ) -> Tuple[Dict[str, Any], ...]:

        service = _create_random_service(key=key, version=version)

        # owner always has full-access
        owner_access = _create_random_access(
            service, gid=service["owner"], execute_access=True, write_access=True
        )

        entry = [
            service,
            owner_access,
        ]
        if team_access:
            entry.append(
                _create_random_access(
                    service,
                    gid=team_gid,
                    execute_access="x" in team_access,
                    write_access="w" in team_access,
                )
            )
        if everyone_access:
            entry.append(
                _create_random_access(
                    service,
                    gid=everyone_gid,
                    execute_access="x" in everyone_access,
                    write_access="w" in everyone_access,
                )
            )
        return tuple(entry)

    return _create_fake


@pytest.fixture()
async def services_catalog(
    aiopg_engine: Engine,
    user_groups_ids: List[int],
    products_names: List[str],
    faker: Faker,
) -> List:

    everyone_gid, user_gid, team_gid = user_groups_ids

    def _create_random_service(**overrides) -> Dict[str, Any]:
        data = dict(
            key=f"simcore/services/{random.choice(['dynamic', 'computational'])}/{faker.name()}",
            version=".".join([faker.pyint() for _ in range(3)]),
            owner=user_gid,
            name=faker.name(),
            description=faker.sentence(),
            thumbnail=random.choice([faker.image_url(), None]),
            classifiers=[],
            quality={},
        )
        data.update(overrides)
        return data

    def _create_random_access(service, **overrides) -> Dict[str, Any]:
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

    def _new_catalog_entry(
        key, version, team_access=None, everyone_access=None
    ) -> Tuple[Dict[str, Any], ...]:
        """ helper to create service entry """

        service = _create_random_service(key=key, version=version)

        # owner always has full-access
        owner_access = _create_random_access(
            service, gid=service["owner"], execute_access=True, write_access=True
        )

        entry = [
            service,
            owner_access,
        ]
        if team_access:
            entry.append(
                _create_random_access(
                    service,
                    gid=team_gid,
                    execute_access="x" in team_access,
                    write_access="w" in team_access,
                )
            )
        if everyone_access:
            entry.append(
                _create_random_access(
                    service,
                    gid=everyone_gid,
                    execute_access="x" in everyone_access,
                    write_access="w" in everyone_access,
                )
            )
        return tuple(entry)

    # ---

    fake_catalog = [
        _new_catalog_entry(
            "simcore/services/dynamic/jupyterlab",
            "1.0.0",
            team_access=None,
            everyone_access=None,
        ),
        _new_catalog_entry(
            "simcore/services/dynamic/jupyterlab",
            "1.0.2",
            team_access="x",
            everyone_access=None,
        ),
    ]

    # pylint: disable=no-value-for-parameter
    stmt_meta = services_meta_data.insert().values([items[0] for items in fake_catalog])
    stmt_access = services_access_rights.insert().values(
        list(itertools.chain(items[1:] for items in fake_catalog))
    )

    async with aiopg_engine.acquire() as conn:
        await conn.execute(stmt_meta)
        await conn.execute(stmt_access)

    yield fake_catalog

    async with aiopg_engine.acquire() as conn:
        await conn.execute(services_access_rights.delete())
        await conn.execute(services_meta_data.delete())


@pytest.fixture
def services_repo(aiopg_engine):
    repo = ServicesRepository(aiopg_engine)
    return repo


async def test_create_service(services_repo, service_catalog_faker):
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


async def test_read_services(aiopg_engine, services_catalog):

    await repo.list_services()

    await repo.get_service()


@pytest.mark.skip(reason="dev")
def test_auto_upgrade(services_catalog):

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
