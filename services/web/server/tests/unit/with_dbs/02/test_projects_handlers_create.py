# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from typing import Any, Callable, Dict, List, Optional

import pytest
from _helpers import ExpectedResponse, MockedStorageSubsystem, standard_role_response
from aiohttp import web
from aiohttp.test_utils import TestClient
from faker import Faker
from models_library.basic_types import UUIDStr
from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_login import UserInfoDict
from simcore_service_webserver._meta import api_version_prefix
from simcore_service_webserver.projects.projects_handlers_crud import (
    ProjectCreate,
    ProjectGet,
)

# HELPERS -----------------------------------------------------------------------------------------


async def _request_create_project(
    client: TestClient,
    project_data: Optional[ProjectCreate] = None,
    *,
    # -> source
    # from_project_uuid: Optional[UUIDStr] = None,
    # -> destination
    # to_template: bool = False
    # to_project_uuid: UUIDStr ??
    as_template: Optional[UUIDStr] = None,  # from_template_uuid
    template_uuid: Optional[UUIDStr] = None,  # to_template_uuid  (client defines uuid!)
    # other options not in the body
    copy_data: bool = True,
    hidden: bool = False,  # not in the body
) -> web.Response:

    url = client.app.router["create_projects"].url_for()
    assert str(url) == f"/{api_version_prefix}/projects"

    params = {}
    if template_uuid:
        params["template_uuid"] = template_uuid
    if as_template:
        params["as_template"] = as_template
    if copy_data:
        params["copy_data"] = copy_data
    if hidden:
        params["hidden"] = copy_data

    if project_data:
        project_data = project_data.dict(exclude_unset=True)

    resp = await client.post(url, params=params, json=project_data)
    return resp


# TESTS -----------------------------------------------------------------------------------------


@pytest.mark.skip(reason="UNDER DEV")
@pytest.mark.parametrize(*standard_role_response())
async def test_new_project(
    client: TestClient,
    logged_user: UserInfoDict,
    primary_group: Dict[str, str],
    faker: Faker,
    expected: ExpectedResponse,
    storage_subsystem_mock,
    project_db_cleaner,
):
    # TODO: fixture with hypothesis on ProjectCreate??
    project_create = ProjectCreate(
        name="Project from test_new_project",
        thumbnail=faker.image_url(widht=60, height=60),
        prj_owner=logged_user["email"],
        access_rights=primary_group,
    )

    resp = await _request_create_project(client, project_create)

    data, _ = await assert_status(resp, expected.created)
    if data:
        project_get = ProjectGet.parse_obj(data)

        assert project_get.dict(
            include=project_create.__fields_set__
        ) == project_create.dict(exclude_unset=True)


@pytest.mark.skip(reason="UNDER DEV")
@pytest.mark.parametrize(*standard_role_response())
async def test_new_project_from_template(
    client,
    logged_user,
    primary_group: Dict[str, str],
    template_project,
    expected,
    storage_subsystem_mock,
    project_db_cleaner,
):
    raise NotImplementedError


@pytest.mark.skip(reason="UNDER DEV")
@pytest.mark.parametrize(*standard_role_response())
async def test_new_project_from_template_with_body(
    client,
    logged_user,
    primary_group: Dict[str, str],
    standard_groups: List[Dict[str, str]],
    template_project,
    expected,
    storage_subsystem_mock,
    project_db_cleaner,
):
    predefined = {
        "uuid": "",
        "name": "Sleepers8",
        "description": "Some lines from user",
        "thumbnail": "",
        "prjOwner": "",
        "creationDate": "2019-06-03T09:59:31.987Z",
        "lastChangeDate": "2019-06-03T09:59:31.987Z",
        "accessRights": {
            str(standard_groups[0]["gid"]): {
                "read": True,
                "write": True,
                "delete": False,
            }
        },
        "workbench": {},
        "tags": [],
        "classifiers": [],
    }
    raise NotImplementedError


@pytest.mark.skip(reason="UNDER DEV")
@pytest.mark.parametrize(*standard_role_response())
async def test_new_template_from_project(
    client: TestClient,
    logged_user: Dict[str, Any],
    primary_group: Dict[str, str],
    all_group: Dict[str, str],
    user_project: Dict[str, Any],
    expected: ExpectedResponse,
    storage_subsystem_mock: MockedStorageSubsystem,
    catalog_subsystem_mock: Callable,
    project_db_cleaner: None,
):
    # POST /v0/projects?as_template={project_uuid}
    url = (
        client.app.router["create_projects"]
        .url_for()
        .with_query(as_template=user_project["uuid"])
    )

    resp = await client.post(f"{url}")
    data, error = await assert_status(resp, expected.created)

    raise NotImplementedError
