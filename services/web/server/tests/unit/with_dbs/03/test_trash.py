# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable
import arrow
import pytest
from aiohttp.test_utils import TestClient
from models_library.api_schemas_webserver.projects import ProjectGet, ProjectListItem
from models_library.rest_pagination import Page
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.webserver_login import UserInfoDict
from servicelib.aiohttp import status
from simcore_service_webserver.db.models import UserRole
from simcore_service_webserver.projects.models import ProjectDict


@pytest.mark.parametrize(
    "user_role",
    [
        UserRole.USER,
    ],
)
@pytest.mark.acceptance_test(
    "For https://github.com/ITISFoundation/osparc-simcore/pull/6579"
)
async def test_trash_projects(
    client: TestClient, logged_user: UserInfoDict, user_project: ProjectDict
):
    assert client.app
    project_uuid = user_project["uuid"]

    url = client.app.router["list_projects"].url_for()
    assert f"{url}" == "/v0/projects"

    # list projects -> non trashed
    resp = await client.get("/v0/projects")
    data, _ = await assert_status(resp, status.HTTP_200_OK)

    page = Page[ProjectListItem].parse_obj(data)
    assert page.meta.total == 1

    got = page.data[0]
    assert got.uuid == project_uuid
    assert got.trashed_at is None
    assert got.trashed_by is None

    resp = await client.get("/v0/projects", filters={"trashed": True})
    data, _ = await assert_status(resp, status.HTTP_200_OK)

    page = Page[ProjectListItem].parse_obj(data)
    assert page.meta.total == 0

    # trash project
    trashing_at = arrow.utcnow().datetime
    resp = await client.get(f"/v0/projects/{project_uuid}:trash")
    data, _ = await assert_status(resp, status.HTTP_200_OK)

    got = ProjectGet.parse_obj(data)
    assert got.uuid == project_uuid

    assert got.trashed_at
    assert trashing_at < got.trashed_at
    assert got.trashed_at < arrow.utcnow().datetime
    assert got.trashed_by == logged_user["name"]

    # get trashed project
    expected = got.copy()

    resp = await client.get(f"/v0/projects/{project_uuid}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    got = ProjectGet.parse_obj(data)
    assert got == expected

    # list trashed projects
    resp = await client.get("/v0/projects", filters={"trashed": True})
    data, _ = await assert_status(resp, status.HTTP_200_OK)

    page = Page[ProjectListItem].parse_obj(data)
    assert page.meta.total == 1
    assert page.data[0].uuid == project_uuid

    # untrash project
    resp = await client.post(f"/v0/projects/{project_uuid}:untrash")
    data, _ = await assert_status(resp, status.HTTP_200_OK)

    got = ProjectGet.parse_obj(data)

    assert got.uuid == project_uuid
    assert got.trashed_at is None
    assert got.trashed_by is None

    # get untrashed project
    expected = got.copy()

    resp = await client.get(f"/v0/projects/{project_uuid}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    got = ProjectGet.parse_obj(data)
    assert got == expected
