# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


import asyncio
import itertools
import random
from typing import Any, Callable, Dict, Iterable, Iterator, List, Tuple

import pytest
import respx
import sqlalchemy as sa
from _pytest.monkeypatch import MonkeyPatch
from aiopg.sa.engine import Engine
from faker import Faker
from fastapi import FastAPI
from pytest_mock.plugin import MockerFixture
from respx.router import MockRouter
from simcore_postgres_database.models.products import products
from simcore_service_catalog.core.application import init_app
from simcore_service_catalog.db.tables import (
    groups,
    services_access_rights,
    services_meta_data,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert
from starlette.testclient import TestClient


@pytest.fixture
def app(
    monkeypatch: MonkeyPatch,
    mocker: MockerFixture,
    service_test_environ: None,
    postgres_db: sa.engine.Engine,
    postgres_host_config: Dict[str, str],
) -> Iterable[FastAPI]:
    monkeypatch.setenv("CATALOG_TRACING", "null")
    app = init_app()
    yield app


@pytest.fixture
def client(loop: asyncio.AbstractEventLoop, app: FastAPI) -> Iterable[TestClient]:
    with TestClient(app) as cli:
        # Note: this way we ensure the events are run in the application
        yield cli


@pytest.fixture()
def director_mockup(app: FastAPI) -> MockRouter:

    with respx.mock(
        base_url=app.state.settings.CATALOG_DIRECTOR.base_url,
        assert_all_called=False,
        assert_all_mocked=True,
    ) as respx_mock:
        respx_mock.head("/", name="healthcheck").respond(200, json={"health": "OK"})
        respx_mock.get("/services", name="list_services").respond(
            200, json={"data": []}
        )
        yield respx_mock


# DATABASE tables fixtures -----------------------------------
#
# These are the tables accessible by the catalog service:
#
# * services_meta_data
#   -> groups(gid)@owner
# * services_access_rights
#   -> groups(gid)@owner,
#   -> products(name)@produt_name
#   -> services_meta_data@key, version
# * services_consume_filetypes
#
# and therefore these are the coupled tables
# - groups
#   -> user, user_to_groups
# - products
#


@pytest.fixture()
async def products_names(aiopg_engine: Engine) -> Iterator[List[str]]:
    """Inits products db table and returns product names"""
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
    """Inits groups table and returns group identifiers"""

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
    """Returns a helper function to init
    services_meta_data and services_access_rights tables

    Can use service_catalog_faker to generate inputs

    Example:
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
            ]
        )
    """
    # pylint: disable=no-value-for-parameter

    async def inject_in_db(fake_catalog: List[Tuple]):
        # [(service, ar1, ...), (service2, ar1, ...) ]

        async with aiopg_engine.acquire() as conn:
            # NOTE: The 'default' dialect with current database version settings does not support in-place multirow inserts
            for service in [items[0] for items in fake_catalog]:
                insert_meta = pg_insert(services_meta_data).values(**service)
                upsert_meta = insert_meta.on_conflict_do_update(
                    index_elements=[
                        services_meta_data.c.key,
                        services_meta_data.c.version,
                    ],
                    set_=service,
                )
                await conn.execute(upsert_meta)

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
    """Returns a fake factory that creates catalog DATA that can be used to fill
    both services_meta_data and services_access_rights tables


    Example:
        fake_service, *fake_access_rights = service_catalog_faker(
                "simcore/services/dynamic/jupyterlab",
                "0.0.1",
                team_access=None,
                everyone_access=None,
                product=target_product,
            ),

        owner_access, team_access, everyone_access = fake_access_rights

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

    def _fake_factory(
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

    return _fake_factory
