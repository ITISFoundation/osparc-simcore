# pylint: disable=not-context-manager
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import uuid
from random import randint
from typing import AsyncIterable, Iterator
from unittest import mock

import httpx
import pytest
import sqlalchemy as sa
from asgi_lifespan import LifespanManager
from faker import Faker
from fastapi import FastAPI
from models_library.projects import ProjectID
from models_library.users import UserID
from pytest import MonkeyPatch
from pytest_mock import MockerFixture
from pytest_simcore.helpers.rawdata_fakers import random_project
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.utils_envs import setenvs_from_dict
from simcore_postgres_database.models.projects import projects
from simcore_postgres_database.models.users import UserRole, UserStatus, users
from simcore_service_resource_usage_tracker.core.application import create_app
from simcore_service_resource_usage_tracker.core.settings import ApplicationSettings


@pytest.fixture(scope="function")
def mock_env(monkeypatch: MonkeyPatch) -> EnvVarsDict:
    """This is the base mock envs used to configure the app.

    Do override/extend this fixture to change configurations
    """
    env_vars: EnvVarsDict = {
        "SC_BOOT_MODE": "production",
        "POSTGRES_CLIENT_NAME": "postgres_test_client",
    }
    setenvs_from_dict(monkeypatch, env_vars)
    return env_vars


@pytest.fixture(scope="function")
async def initialized_app(
    mock_env: EnvVarsDict,
    postgres_db: sa.engine.Engine,
    postgres_host_config: dict[str, str],
) -> AsyncIterable[FastAPI]:
    settings = ApplicationSettings.create_from_envs()
    app = create_app(settings)
    async with LifespanManager(app):
        yield app


@pytest.fixture(scope="function")
async def async_client(initialized_app: FastAPI) -> AsyncIterable[httpx.AsyncClient]:
    async with httpx.AsyncClient(
        app=initialized_app,
        base_url="http://resource-usage-tracker.testserver.io",
        headers={"Content-Type": "application/json"},
    ) as client:
        yield client


@pytest.fixture
def mocked_prometheus(mocker: MockerFixture) -> mock.Mock:
    mocked_get_prometheus_api_client = mocker.patch(
        "simcore_service_resource_usage_tracker.modules.prometheus_containers.core.get_prometheus_api_client",
        autospec=True,
    )
    return mocked_get_prometheus_api_client


@pytest.fixture()
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
def project_uuid() -> ProjectID:
    return ProjectID(f"{uuid.uuid4()}")


@pytest.fixture()
def project_db(
    postgres_db: sa.engine.Engine,
    project_uuid: ProjectID,
    user_id: UserID,
    faker: Faker,
) -> Iterator[dict]:
    with postgres_db.connect() as con:
        suffix = faker.word()
        # removes all projects before continuing
        con.execute(projects.delete())
        result = con.execute(
            projects.insert()
            .values(
                **random_project(
                    prj_owner=user_id,
                    uuid=project_uuid,
                    workbench={
                        "2b231c38-0ebc-5cc0-1234-1ffe573f54e9": {
                            "key": f"simcore/services/comp/test_{__name__}_{suffix}",
                            "version": "1.2.3",
                            "label": f"test_{__name__}_{suffix}",
                            "inputs": {"x": faker.pyint(), "y": faker.pyint()},
                        }
                    },
                )
            )
            .returning(projects)
        )
        project = result.first()
        assert project
        yield dict(project)

        con.execute(projects.delete().where(projects.c.uuid == f"{project_uuid}"))
