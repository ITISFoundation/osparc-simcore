# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import contextlib
from collections.abc import AsyncIterator

import pytest
from aiohttp.test_utils import TestClient
from models_library.api_schemas_webserver.projects import ProjectGet
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.webserver_login import UserInfoDict
from servicelib.aiohttp import status
from simcore_service_webserver.db.models import UserRole
from simcore_service_webserver.projects import _trash_service
from simcore_service_webserver.projects.models import ProjectDict
from simcore_service_webserver.trash._service import delete_expired_trash


@pytest.fixture
def app_environment(
    app_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch
) -> EnvVarsDict:
    return app_environment | setenvs_from_dict(
        monkeypatch, {"TRASH_RETENTION_DAYS": "0"}
    )


@pytest.fixture
def user_role() -> UserRole:
    return UserRole.USER


@contextlib.asynccontextmanager
async def _client_session_with_user(
    client: TestClient, user: UserInfoDict
) -> AsyncIterator[TestClient]:
    assert client.app

    url = client.app.router["logout"].url_for()
    resp = await client.post(f"{url}")
    await assert_status(resp, status.HTTP_200_OK)

    url = client.app.router["login"].url_for()
    resp = await client.post(
        f"{url}",
        json={
            "email": user["email"],
            "password": user["raw_password"],
        },
    )
    await assert_status(resp, status.HTTP_200_OK)

    yield client

    url = client.app.router["logout"].url_for()
    resp = await client.post(f"{url}")
    await assert_status(resp, status.HTTP_200_OK)


async def test_trash_service__delete_expired_trash(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    other_user: UserInfoDict,
    other_user_project: ProjectDict,
    mocked_catalog: None,
    mocked_director_v2: None,
):
    assert client.app
    assert logged_user["id"] != other_user["id"]

    # TRASH projects
    # logged_user trashes his project
    user_project_id = user_project["uuid"]
    await _trash_service.trash_project(
        client.app,
        product_name="osparc",
        user_id=logged_user["id"],
        project_id=user_project_id,
        force_stop_first=True,
        explicit=True,
    )

    # other_user trashes his project
    other_user_project_id = other_user_project["uuid"]
    await _trash_service.trash_project(
        client.app,
        product_name="osparc",
        user_id=other_user["id"],
        project_id=other_user_project_id,
        force_stop_first=True,
        explicit=True,
    )

    resp = await client.get(f"/v0/projects/{user_project_id}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert ProjectGet.model_validate(data).trashed_by == logged_user["primary_gid"]

    # UNDER TEST: Run delete_expired_trash
    await delete_expired_trash(client.app)

    # ASSERT: logged_user tries to get the project and expects 404
    resp = await client.get(f"/v0/projects/{user_project_id}")
    await assert_status(resp, status.HTTP_404_NOT_FOUND)

    # ASSERT: other_user tries to get the project and expects 404
    async with _client_session_with_user(client, other_user):
        resp = await client.get(f"/v0/projects/{other_user_project_id}")
        await assert_status(resp, status.HTTP_404_NOT_FOUND)
