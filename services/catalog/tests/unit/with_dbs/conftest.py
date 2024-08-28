# pylint: disable=not-context-manager
# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import itertools
from collections.abc import AsyncIterator, Awaitable, Callable
from copy import deepcopy
from datetime import datetime
from typing import Any

import pytest
import sqlalchemy as sa
from faker import Faker
from fastapi.encoders import jsonable_encoder
from models_library.products import ProductName
from models_library.services import ServiceMetaDataPublished
from models_library.users import UserID
from pydantic import Extra, parse_obj_as
from pytest_simcore.helpers.faker_factories import (
    random_service_access_rights,
    random_service_meta_data,
)
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.postgres_tools import (
    PostgresTestConfig,
    insert_and_get_row_lifespan,
)
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_postgres_database.models.products import products
from simcore_postgres_database.models.users import users
from simcore_service_catalog.core.settings import ApplicationSettings
from simcore_service_catalog.db.tables import (
    groups,
    services_access_rights,
    services_meta_data,
)
from sqlalchemy import tuple_
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncEngine


@pytest.fixture
def app_environment(
    monkeypatch: pytest.MonkeyPatch,
    app_environment: EnvVarsDict,
    postgres_env_vars_dict: EnvVarsDict,
) -> EnvVarsDict:
    return setenvs_from_dict(
        monkeypatch,
        {
            **app_environment,
            **postgres_env_vars_dict,
            "SC_BOOT_MODE": "local-development",
            "POSTGRES_CLIENT_NAME": "pytest_client",
        },
    )


@pytest.fixture
async def app_settings(  # starts postgres service before app starts
    postgres_db: sa.engine.Engine,
    postgres_host_config: PostgresTestConfig,
    app_settings: ApplicationSettings,
) -> ApplicationSettings:
    # Database is init BEFORE app
    assert postgres_db
    print("database started:", postgres_host_config)

    # Ensures both postgres service and app environs are the same!
    assert app_settings
    assert app_settings.CATALOG_POSTGRES
    assert postgres_host_config["user"] == app_settings.CATALOG_POSTGRES.POSTGRES_USER
    assert postgres_host_config["database"] == app_settings.CATALOG_POSTGRES.POSTGRES_DB
    assert (
        app_settings.CATALOG_POSTGRES.POSTGRES_PASSWORD.get_secret_value()
        == postgres_host_config["password"]
    )
    return app_settings


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


@pytest.fixture
async def product(
    product: dict[str, Any],
    sqlalchemy_async_engine: AsyncEngine,
) -> AsyncIterator[dict[str, Any]]:
    """
    injects product in db
    """
    # NOTE: this fixture ignores products' group-id but it is fine for this test context
    assert product["group_id"] is None
    async with insert_and_get_row_lifespan(
        sqlalchemy_async_engine,
        table=products,
        values=product,
        pk_col=products.c.name,
        pk_value=product["name"],
    ) as row:
        yield row


@pytest.fixture
def target_product(product: dict[str, Any], product_name: ProductName) -> ProductName:
    assert product_name == parse_obj_as(ProductName, product["name"])
    return product_name


@pytest.fixture
def other_product(product: dict[str, Any]) -> ProductName:
    other = parse_obj_as(ProductName, "osparc")
    assert other != product["name"]
    return other


@pytest.fixture
def products_names(
    target_product: ProductName, other_product: ProductName
) -> list[str]:
    return [other_product, target_product]


@pytest.fixture
async def user(
    user: dict[str, Any],
    user_id: UserID,
    sqlalchemy_async_engine: AsyncEngine,
) -> AsyncIterator[dict[str, Any]]:
    """
    injects a user in db
    """
    assert user_id == user["id"]
    async with insert_and_get_row_lifespan(
        sqlalchemy_async_engine,
        table=users,
        values=user,
        pk_col=users.c.id,
        pk_value=user["id"],
    ) as row:
        yield row


@pytest.fixture()
async def user_groups_ids(
    sqlalchemy_async_engine: AsyncEngine, user: dict[str, Any]
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
            await conn.execute(
                groups.insert().values(**dict(zip(cols, row, strict=False)))
            )

    gids = [1, user["primary_gid"]] + [items[0] for items in data]

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

    Can use `create_fake_service_data` to generate inputs

    Example:
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
            ]
        )
    """
    # pylint: disable=no-value-for-parameter
    inserted_services: set[tuple[str, str]] = set()

    async def _inject_in_db(fake_catalog: list[tuple]):
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

    yield _inject_in_db

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

        assert ServiceMetaDataPublished.parse_obj(
            data
        ), "Invalid fake data. Out of sync!"
        return data

    return _fake_factory


@pytest.fixture()
async def create_fake_service_data(
    user_groups_ids: list[int],
    products_names: list[str],
    faker: Faker,
) -> Callable:
    """Returns a fake factory that creates catalog DATA that can be used to fill
    both services_meta_data and services_access_rights tables


    Example:
        fake_service, *fake_access_rights = create_fake_service_data(
                "simcore/services/dynamic/jupyterlab",
                "0.0.1",
                team_access="xw",
                everyone_access="x",
                product=target_product,
            ),

        owner_access, team_access, everyone_access = fake_access_rights

    """
    everyone_gid, user_gid, team_gid = user_groups_ids

    def _random_service(**overrides) -> dict[str, Any]:
        return random_service_meta_data(
            owner_primary_gid=user_gid,
            fake=faker,
            **overrides,
        )

    def _random_access(service, **overrides) -> dict[str, Any]:
        return random_service_access_rights(
            key=service["key"],
            version=service["version"],
            fake=faker,
            **overrides,
        )

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
def create_director_list_services_from() -> Callable[
    [list[dict[str, Any]], list], list[dict[str, Any]]
]:
    """Convenience function to merge outputs of
    - `create_fake_service_data` callable with those of
    - `expected_director_list_services` fixture

    to produce a new expected_director_list_services
    """

    class _Loader(ServiceMetaDataPublished):
        class Config:
            extra = Extra.ignore
            allow_population_by_field_name = True

    def _(
        expected_director_list_services: list[dict[str, Any]],
        fake_services_data: list,
    ):
        return [
            jsonable_encoder(
                _Loader.parse_obj(
                    {
                        **next(itertools.cycle(expected_director_list_services)),
                        **data[0],  # service, **access_rights = data
                    }
                ),
                exclude_unset=True,
            )
            for data in fake_services_data
        ]

    return _
