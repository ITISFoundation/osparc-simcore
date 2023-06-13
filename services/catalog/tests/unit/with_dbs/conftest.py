# pylint: disable=not-context-manager
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import itertools
import random
from copy import deepcopy
from datetime import datetime
from random import randint
from typing import Any, AsyncIterator, Awaitable, Callable, Iterator

import pytest
import respx
import sqlalchemy as sa
from faker import Faker
from fastapi import FastAPI
from models_library.services import ServiceDockerData
from models_library.users import UserID
from pytest import MonkeyPatch
from pytest_mock.plugin import MockerFixture
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.utils_postgres import PostgresTestConfig
from simcore_postgres_database.models.products import products
from simcore_postgres_database.models.users import UserRole, UserStatus, users
from simcore_service_catalog.core.application import init_app
from simcore_service_catalog.db.tables import (
    groups,
    services_access_rights,
    services_meta_data,
)
from sqlalchemy import tuple_
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncEngine
from starlette.testclient import TestClient


@pytest.fixture()
async def products_names(
    sqlalchemy_async_engine: AsyncEngine,
) -> AsyncIterator[list[str]]:
    """Inits products db table and returns product names"""
    data = [
        # already upon creation: ("osparc", r"([\.-]{0,1}osparc[\.-])"),
        ("s4l", r"(^s4l[\.-])|(^sim4life\.)|(^api.s4l[\.-])|(^api.sim4life\.)"),
        ("tis", r"(^tis[\.-])|(^ti-solutions\.)"),
    ]

    # pylint: disable=no-value-for-parameter

    async with sqlalchemy_async_engine.begin() as conn:
        # NOTE: The 'default' dialect with current database version settings does not support in-place multirow inserts
        for n, (name, regex) in enumerate(data):
            stmt = products.insert().values(name=name, host_regex=regex, priority=n)
            await conn.execute(stmt)

    names = [
        "osparc",
    ] + [items[0] for items in data]

    yield names

    async with sqlalchemy_async_engine.begin() as conn:
        await conn.execute(products.delete())


@pytest.fixture
def app(
    monkeypatch: MonkeyPatch,
    mocker: MockerFixture,
    service_test_environ: EnvVarsDict,
    postgres_db: sa.engine.Engine,
    postgres_host_config: PostgresTestConfig,
    products_names: list[str],
) -> FastAPI:
    print("database started:", postgres_host_config)
    print("database w/products in table:", products_names)

    # Ensures both postgres service and app environs are the same!
    assert service_test_environ["POSTGRES_USER"] == postgres_host_config["user"]
    assert service_test_environ["POSTGRES_DB"] == postgres_host_config["database"]
    assert service_test_environ["POSTGRES_PASSWORD"] == postgres_host_config["password"]

    monkeypatch.setenv("SC_BOOT_MODE", "local-development")
    monkeypatch.setenv("POSTGRES_CLIENT_NAME", "pytest_client")
    app = init_app()

    return app


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as cli:
        # Note: this way we ensure the events are run in the application
        yield cli


@pytest.fixture()
def director_mockup(app: FastAPI) -> Iterator[respx.MockRouter]:
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


@pytest.fixture(scope="session")
def user_id() -> UserID:
    return UserID(randint(1, 10000))


@pytest.fixture()
def user_db(postgres_db: sa.engine.Engine, user_id: UserID) -> Iterator[dict]:
    with postgres_db.connect() as con:
        # removes all users before continuing
        con.execute(users.delete())
        con.execute(
            users.insert()
            .values(
                id=user_id,
                name="test user",
                email="test@user.com",
                password_hash="testhash",
                status=UserStatus.ACTIVE,
                role=UserRole.USER,
            )
            .returning(sa.literal_column("*"))
        )
        # this is needed to get the primary_gid correctly
        result = con.execute(sa.select(users).where(users.c.id == user_id))
        user = result.first()
        assert user
        yield dict(user)

        con.execute(users.delete().where(users.c.id == user_id))


@pytest.fixture()
async def user_groups_ids(
    sqlalchemy_async_engine: AsyncEngine, user_db: dict[str, Any]
) -> AsyncIterator[list[int]]:
    """Inits groups table and returns group identifiers"""

    cols = ("gid", "name", "description", "type", "thumbnail", "inclusion_rules")
    data = [
        (
            20001,
            "Team Black",
            "External testers",
            "STANDARD",
            "http://mib.org",
            {"email": "@(foo|testers|mib)+.(org|com)$"},
        )
    ]
    # pylint: disable=no-value-for-parameter
    async with sqlalchemy_async_engine.begin() as conn:
        for row in data:
            # NOTE: The 'default' dialect with current database version settings does not support in-place multirow inserts
            await conn.execute(groups.insert().values(**dict(zip(cols, row))))

    gids = [1, user_db["primary_gid"]] + [items[0] for items in data]

    yield gids

    async with sqlalchemy_async_engine.begin() as conn:
        await conn.execute(services_meta_data.delete())
        await conn.execute(groups.delete().where(groups.c.gid.in_(gids[2:])))


@pytest.fixture()
async def services_db_tables_injector(
    sqlalchemy_async_engine: AsyncEngine,
) -> AsyncIterator[Callable[[list[tuple]], Awaitable[None]]]:
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
    inserted_services: set[tuple[str, str]] = set()

    async def inject_in_db(fake_catalog: list[tuple]):
        # [(service, ar1, ...), (service2, ar1, ...) ]

        async with sqlalchemy_async_engine.begin() as conn:
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
                inserted_services.add((service["key"], service["version"]))

            for access_rights in itertools.chain(items[1:] for items in fake_catalog):
                stmt_access = services_access_rights.insert().values(access_rights)
                await conn.execute(stmt_access)

    yield inject_in_db

    async with sqlalchemy_async_engine.begin() as conn:
        await conn.execute(
            services_meta_data.delete().where(
                tuple_(services_meta_data.c.key, services_meta_data.c.version).in_(
                    inserted_services
                )
            )
        )


@pytest.fixture()
async def service_metadata_faker(faker: Faker) -> Callable:
    """Returns a factory to produce fake
    service metadata
    """
    template = {
        "integration-version": "1.0.0",
        "key": "simcore/services/comp/itis/sleeper",
        "version": "2.1.4",
        "type": "computational",
        "name": "sleeper",
        "authors": [
            {
                "name": faker.name(),
                "email": faker.email(),
                "affiliation": "IT'IS Foundation",
            },
        ],
        "contact": faker.email(),
        "description": "A service which awaits for time to pass, two times.",
        "inputs": {
            "input_1": {
                "displayOrder": 1,
                "label": "File with int number",
                "description": "Pick a file containing only one integer",
                "type": "data:text/plain",
                "fileToKeyMap": {"single_number.txt": "input_1"},
            },
            "input_2": {
                "displayOrder": 2,
                "label": "Sleep interval",
                "description": "Choose an amount of time to sleep in range [0-5]",
                "defaultValue": 2,
                "type": "ref_contentSchema",
                "contentSchema": {
                    "title": "Sleep interval",
                    "type": "integer",
                    "x_unit": "second",
                    "minimum": 0,
                    "maximum": 5,
                },
            },
            "input_3": {
                "displayOrder": 3,
                "label": "Fail after sleep",
                "description": "If set to true will cause service to fail after it sleeps",
                "type": "boolean",
                "defaultValue": False,
            },
            "input_4": {
                "displayOrder": 4,
                "label": "Distance to bed",
                "description": "It will first walk the distance to bed",
                "defaultValue": 0,
                "type": "ref_contentSchema",
                "contentSchema": {
                    "title": "Distance to bed",
                    "type": "integer",
                    "x_unit": "meter",
                },
            },
        },
        "outputs": {
            "output_1": {
                "displayOrder": 1,
                "label": "File containing one random integer",
                "description": "Integer is generated in range [1-9]",
                "type": "data:text/plain",
                "fileToKeyMap": {"single_number.txt": "output_1"},
            },
            "output_2": {
                "displayOrder": 2,
                "label": "Random sleep interval",
                "description": "Interval is generated in range [1-9]",
                "type": "ref_contentSchema",
                "contentSchema": {
                    "title": "Random sleep interval",
                    "type": "integer",
                    "x_unit": "second",
                },
            },
        },
    }

    def _fake_factory(**overrides):
        data = deepcopy(template)
        data.update(**overrides)

        assert ServiceDockerData.parse_obj(data), "Invalid fake data. Out of sync!"
        return data

    return _fake_factory


@pytest.fixture()
async def service_catalog_faker(
    user_groups_ids: list[int],
    products_names: list[str],
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

    def _random_service(**overrides) -> dict[str, Any]:
        data = dict(
            key=f"simcore/services/{random.choice(['dynamic', 'computational'])}/{faker.name()}",
            version=".".join([str(faker.pyint()) for _ in range(3)]),
            owner=user_gid,
            name=faker.name(),
            description=faker.sentence(),
            thumbnail=random.choice([faker.image_url(), None]),
            classifiers=[],
            quality={},
            deprecated=None,
        )
        data.update(overrides)
        return data

    def _random_access(service, **overrides) -> dict[str, Any]:
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
        key,
        version,
        team_access=None,
        everyone_access=None,
        product=products_names[0],
        deprecated: datetime | None = None,
    ) -> tuple[dict[str, Any], ...]:
        service = _random_service(key=key, version=version, deprecated=deprecated)

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


@pytest.fixture
def mock_catalog_background_task(mocker: MockerFixture) -> None:
    """patch the setup of the background task so we can call it manually"""
    mocker.patch(
        "simcore_service_catalog.core.events.start_registry_sync_task",
        return_value=None,
        autospec=True,
    )
    mocker.patch(
        "simcore_service_catalog.core.events.stop_registry_sync_task",
        return_value=None,
        autospec=True,
    )
