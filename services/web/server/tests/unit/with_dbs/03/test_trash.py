# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable
from collections.abc import Callable
from uuid import UUID

import arrow
import pytest
from aiohttp.test_utils import TestClient
from aioresponses import aioresponses
from models_library.api_schemas_webserver.projects import ProjectGet, ProjectListItem
from models_library.rest_pagination import Page
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.webserver_login import UserInfoDict
from servicelib.aiohttp import status
from simcore_service_webserver.db.models import UserRole
from simcore_service_webserver.projects.models import ProjectDict


@pytest.fixture
def user_role() -> UserRole:
    return UserRole.USER


@pytest.fixture
def mocked_catalog(
    user_project: ProjectDict,
    catalog_subsystem_mock: Callable[[list[ProjectDict]], None],
):
    catalog_subsystem_mock([user_project])


@pytest.mark.acceptance_test(
    "For https://github.com/ITISFoundation/osparc-simcore/pull/6579"
)
async def test_trash_projects(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    mocked_catalog: None,
    director_v2_service_mock: aioresponses,
):
    assert client.app

    project_uuid = UUID(user_project["uuid"])

    url = client.app.router["list_projects"].url_for()
    assert f"{url}" == "/v0/projects"

    # LIST NOT trashed
    resp = await client.get("/v0/projects")
    await assert_status(resp, status.HTTP_200_OK)

    page = Page[ProjectListItem].parse_obj(await resp.json())
    assert page.meta.total == 1

    got = page.data[0]
    assert got.uuid == project_uuid
    assert got.trashed_at is None

    # LIST trashed
    resp = await client.get("/v0/projects", params={"filters": '{"trashed": true}'})
    await assert_status(resp, status.HTTP_200_OK)

    page = Page[ProjectListItem].parse_obj(await resp.json())
    assert page.meta.total == 0

    # TRASH
    trashing_at = arrow.utcnow().datetime
    resp = await client.post(f"/v0/projects/{project_uuid}:trash")
    await assert_status(resp, status.HTTP_204_NO_CONTENT)

    # GET
    resp = await client.get(f"/v0/projects/{project_uuid}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    got = ProjectGet.parse_obj(data)
    assert got.uuid == project_uuid

    assert got.trashed_at
    assert trashing_at < got.trashed_at
    assert got.trashed_at < arrow.utcnow().datetime

    # LIST trashed
    resp = await client.get("/v0/projects", params={"filters": '{"trashed": true}'})
    await assert_status(resp, status.HTTP_200_OK)

    page = Page[ProjectListItem].parse_obj(await resp.json())
    assert page.meta.total == 1
    assert page.data[0].uuid == project_uuid

    # UNTRASH
    resp = await client.post(f"/v0/projects/{project_uuid}:untrash")
    data, _ = await assert_status(resp, status.HTTP_204_NO_CONTENT)

    # GET
    resp = await client.get(f"/v0/projects/{project_uuid}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    got = ProjectGet.parse_obj(data)

    assert got.uuid == project_uuid
    assert got.trashed_at is None
