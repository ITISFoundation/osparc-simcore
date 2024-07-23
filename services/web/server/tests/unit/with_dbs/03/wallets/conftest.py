# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import json
from collections.abc import AsyncIterator, Iterator
from copy import deepcopy
from pathlib import Path

import pytest
import sqlalchemy as sa
from aioresponses import aioresponses
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.webserver_login import UserInfoDict
from pytest_simcore.helpers.webserver_projects import NewProject, delete_all_projects
from simcore_postgres_database.models.wallets import wallets
from simcore_service_webserver.application_settings import ApplicationSettings


@pytest.fixture
def app_environment(
    app_environment: EnvVarsDict,
    env_devel_dict: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
):
    new_envs = setenvs_from_dict(
        monkeypatch,
        {
            **env_devel_dict,
            **app_environment,  # WARNING: AFTER env_devel_dict because HOST are set to 127.0.0.1 in here
            "PAYMENTS_FAKE_COMPLETION": "0",  # Completion is done manually
            "WEBSERVER_DB_LISTENER": "0",
            "WEBSERVER_DEV_FEATURES_ENABLED": "1",
            "WEBSERVER_GARBAGE_COLLECTOR": "null",
            "PAYMENTS_FAKE_GATEWAY_URL": "https://some-fake-gateway.com",
        },
    )

    settings = ApplicationSettings.create_from_envs()

    new_envs_json = json.dumps(new_envs, sort_keys=True, indent=1)

    assert settings.WEBSERVER_WALLETS is True, f"{new_envs_json}"
    assert settings.WEBSERVER_PAYMENTS is not None, f"{new_envs_json}"

    return new_envs


@pytest.fixture
def wallets_clean_db(postgres_db: sa.engine.Engine) -> Iterator[None]:
    with postgres_db.connect() as con:
        yield
        con.execute(wallets.delete())


@pytest.fixture
async def shared_project(
    client,
    fake_project,
    logged_user,
    all_group,
    tests_data_dir: Path,
    osparc_product_name: str,
):
    fake_project.update(
        {
            "accessRights": {
                f"{all_group['gid']}": {"read": True, "write": False, "delete": False}
            },
        },
    )
    async with NewProject(
        fake_project,
        client.app,
        user_id=logged_user["id"],
        tests_data_dir=tests_data_dir,
        product_name=osparc_product_name,
    ) as project:
        print("-----> added project", project["name"])
        yield project
        print("<----- removed project", project["name"])


@pytest.fixture
async def template_project(
    client,
    fake_project,
    logged_user,
    all_group: dict[str, str],
    tests_data_dir: Path,
    osparc_product_name: str,
    user: UserInfoDict,
):
    project_data = deepcopy(fake_project)
    project_data["name"] = "Fake template"
    project_data["uuid"] = "d4d0eca3-d210-4db6-84f9-63670b07176b"
    project_data["accessRights"] = {
        str(all_group["gid"]): {"read": True, "write": False, "delete": False}
    }

    async with NewProject(
        project_data,
        client.app,
        user_id=user["id"],
        tests_data_dir=tests_data_dir,
        product_name=osparc_product_name,
    ) as template_project:
        print("-----> added template project", template_project["name"])
        yield template_project
        print("<----- removed template project", template_project["name"])


@pytest.fixture
async def project_db_cleaner(client):
    yield
    await delete_all_projects(client.app)


@pytest.fixture()
async def director_v2_automock(
    director_v2_service_mock: aioresponses,
) -> AsyncIterator[aioresponses]:
    return director_v2_service_mock
