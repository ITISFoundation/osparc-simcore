# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

from typing import Any, Callable, Iterator, cast

import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from pytest import FixtureRequest, MonkeyPatch
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.utils_envs import setenvs_from_dict
from simcore_postgres_database.models.groups import groups
from simcore_postgres_database.models.groups_extra_properties import (
    groups_extra_properties,
)
from simcore_postgres_database.models.products import products
from simcore_service_director_v2.modules.db.repositories.groups_extra_properties import (
    GroupsExtraPropertiesRepository,
)
from simcore_service_director_v2.utils.db import get_repository

pytest_simcore_core_services_selection = [
    "postgres",
]
pytest_simcore_ops_services_selection = [
    "adminer",
]


@pytest.fixture
def mock_env(
    monkeypatch: MonkeyPatch,
    mock_env: EnvVarsDict,
    postgres_host_config: dict[str, str],
    postgres_db: sa.engine.Engine,
) -> EnvVarsDict:
    """overrides unit/conftest:mock_env fixture"""
    env_vars = mock_env.copy()
    env_vars.update(
        {
            "S3_ACCESS_KEY": "12345678",
            "S3_BUCKET_NAME": "simcore",
            "S3_ENDPOINT": "http://172.17.0.1:9001",
            "S3_SECRET_KEY": "12345678",
            "S3_SECURE": "False",
            "POSTGRES_HOST": postgres_host_config["host"],
            "POSTGRES_USER": postgres_host_config["user"],
            "POSTGRES_PASSWORD": postgres_host_config["password"],
            "POSTGRES_DB": postgres_host_config["database"],
        }
    )
    setenvs_from_dict(monkeypatch, env_vars)

    # NOTE: drops the default internet policy added by the migration to test
    # otherwise any user will always have access to the internet
    with postgres_db.connect() as con:
        con.execute(
            groups_extra_properties.delete(groups_extra_properties.c.group_id == 1)
        )
    return env_vars


@pytest.fixture()
def give_internet_to_group(
    postgres_db: sa.engine.Engine,
) -> Iterator[Callable[..., dict]]:
    to_remove = []

    def creator(
        group_id: int, has_internet_access: bool, product_name: str = None
    ) -> dict[str, Any]:
        with postgres_db.connect() as con:
            groups_extra_properties_config = {
                "group_id": group_id,
                "internet_access": has_internet_access,
            }
            if product_name:
                groups_extra_properties_config["product_name"] = product_name

            con.execute(
                groups_extra_properties.insert()
                .values(groups_extra_properties_config)
                .returning(sa.literal_column("*"))
            )
            # this is needed to get the primary_gid correctly
            result = con.execute(
                sa.select(groups_extra_properties).where(
                    groups_extra_properties.c.group_id == group_id
                )
            )
            entry = result.first()
            assert entry
            print(f"--> created {entry=}")
            to_remove.append(group_id)

        return dict(entry)

    yield creator

    with postgres_db.connect() as con:
        con.execute(
            groups_extra_properties.delete().where(
                groups_extra_properties.c.group_id.in_(to_remove)
            )
        )
    print(f"<-- deleted groups_extra_properties {to_remove=}")


@pytest.fixture(params=[True, False])
def with_internet_access(request: FixtureRequest) -> bool:
    return request.param


@pytest.fixture()
async def user(
    mock_env: EnvVarsDict,
    registered_user: Callable[..., dict],
    give_internet_to_group: Callable[..., dict],
    with_internet_access: bool,
) -> dict[str, Any]:
    user = registered_user()
    group_info = give_internet_to_group(
        group_id=user["primary_gid"], has_internet_access=with_internet_access
    )
    user["product_name"] = group_info["product_name"]
    return user


async def test_has_internet_access(
    initialized_app: FastAPI,
    user: dict[str, Any],
    with_internet_access: bool,
):
    groups_extra_properties = cast(
        GroupsExtraPropertiesRepository,
        get_repository(initialized_app, GroupsExtraPropertiesRepository),
    )
    allow_internet_access: bool = await groups_extra_properties.has_internet_access(
        user_id=user["id"], product_name=user["product_name"]
    )
    assert allow_internet_access is with_internet_access


async def test_regression_group_id_is_not_unique(
    mock_env: EnvVarsDict, postgres_db: sa.engine.Engine
):
    def _get_group_id(con: sa.engine.Connection) -> int:
        groups_config = {"name": "", "description": ""}
        result = con.execute(
            groups.insert().values(groups_config).returning(sa.literal_column("*"))
        )
        return result.first()[0]

    def _insert_product(con: sa.engine.Connection, group_id: int, name: str) -> int:
        product_config = {"name": name, "group_id": group_id, "host_regex": ""}
        con.execute(products.insert().values(product_config))

    def _insert_groups_extra_properties(
        con: sa.engine.Connection, group_id: int, product_name: str
    ) -> int:
        groups_extra_properties_config = {
            "product_name": product_name,
            "group_id": group_id,
        }
        con.execute(
            groups_extra_properties.insert().values(groups_extra_properties_config)
        )

    with postgres_db.connect() as con:
        group_id_1 = _get_group_id(con)
        group_id_2 = _get_group_id(con)

        # create product 1 and product 2
        _insert_product(con, group_id_1, "p1")
        _insert_product(con, group_id_2, "p2")

        # these worked before
        _insert_groups_extra_properties(con, group_id_1, "p1")
        _insert_groups_extra_properties(con, group_id_2, "p2")

        # these were broken before
        _insert_groups_extra_properties(con, group_id_1, "p2")
        _insert_groups_extra_properties(con, group_id_2, "p1")

        # downgrade will fail since we have duplicates,
        # duplicate group_id were always supposed to be supported
        con.execute(groups_extra_properties.delete())
