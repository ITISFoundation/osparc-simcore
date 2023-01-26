# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

from typing import Any, Callable, Iterator, cast

import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from pytest import FixtureRequest, MonkeyPatch
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.utils_envs import setenvs_from_dict
from simcore_postgres_database.models.groups_extra_properties import (
    groups_extra_properties,
)
from simcore_service_director_v2.modules.db.repositories.groups_extra_properties import (
    InternetToGroupsRepository,
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
    postgres_host_config: dict[str, str],
    mock_env: EnvVarsDict,
) -> EnvVarsDict:
    """overrides unit/conftest:mock_env fixture"""
    env_vars = mock_env.copy()
    env_vars.update(
        {
            "DIRECTOR_V2_POSTGRES_ENABLED": "true",
            "S3_ACCESS_KEY": "12345678",
            "S3_BUCKET_NAME": "simcore",
            "S3_ENDPOINT": "http://172.17.0.1:9001",
            "S3_SECRET_KEY": "12345678",
            "S3_SECURE": "False",
        }
    )
    setenvs_from_dict(monkeypatch, env_vars)
    return env_vars


@pytest.fixture()
def internet_to_group(postgres_db: sa.engine.Engine) -> Iterator[Callable[..., dict]]:
    created_group_ids = []

    def creator(**groups_extra_properties_kwargs) -> dict[str, Any]:
        with postgres_db.connect() as con:
            # removes all users before continuing
            groups_extra_properties_config = {
                "group_id": len(created_group_ids) + 1,
                "has_access": True,
            }
            groups_extra_properties_config.update(groups_extra_properties_kwargs)

            con.execute(
                groups_extra_properties.insert()
                .values(groups_extra_properties_config)
                .returning(sa.literal_column("*"))
            )
            # this is needed to get the primary_gid correctly
            result = con.execute(
                sa.select([groups_extra_properties]).where(
                    groups_extra_properties.c.group_id
                    == groups_extra_properties_config["group_id"]
                )
            )
            entry = result.first()
            assert entry
            print(f"--> created {entry=}")
            created_group_ids.append(entry["group_id"])
        return dict(entry)

    yield creator

    with postgres_db.connect() as con:
        con.execute(
            groups_extra_properties.delete().where(
                groups_extra_properties.c.group_id.in_(created_group_ids)
            )
        )
    print(f"<-- deleted groups_extra_properties {created_group_ids=}")


@pytest.fixture(params=[True, False])
def with_internet_access(request: FixtureRequest) -> bool:
    return request.param


@pytest.fixture()
async def user(
    mock_env: EnvVarsDict,
    registered_user: Callable[..., dict],
    internet_to_group: Callable[..., dict],
    with_internet_access: bool,
) -> dict[str, Any]:
    user = registered_user()
    if with_internet_access:
        internet_to_group(group_id=user["primary_gid"])
    return user


async def test_has_access(
    initialized_app: FastAPI, user: dict[str, Any], with_internet_access: bool
):
    groups_extra_properties = cast(
        InternetToGroupsRepository,
        get_repository(initialized_app, InternetToGroupsRepository),
    )
    allow_internet_access: bool = await groups_extra_properties.has_access(
        user_id=user["id"]
    )
    assert allow_internet_access is with_internet_access
