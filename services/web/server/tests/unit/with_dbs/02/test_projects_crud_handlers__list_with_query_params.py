# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-statements

import json
import random
from collections import UserDict
from collections.abc import Iterator
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
import sqlalchemy as sa
from aiohttp.test_utils import TestClient
from models_library.folders import FolderID
from models_library.projects import ProjectID, ProjectTemplateType
from models_library.users import UserID
from pydantic import BaseModel, PositiveInt
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.webserver_login import UserInfoDict
from pytest_simcore.helpers.webserver_parametrizations import (
    ExpectedResponse,
    standard_role_response,
)
from pytest_simcore.helpers.webserver_projects import create_project
from servicelib.aiohttp import status
from simcore_postgres_database.models.folders_v2 import folders_v2
from simcore_postgres_database.models.projects_to_folders import projects_to_folders
from simcore_service_webserver._meta import api_version_prefix
from simcore_service_webserver.db.models import UserRole
from simcore_service_webserver.projects.models import ProjectDict


def standard_user_role() -> tuple[str, tuple[UserRole, ExpectedResponse]]:
    all_roles = standard_role_response()

    return (all_roles[0], [pytest.param(*all_roles[1][2], id="standard_user_role")])


def standard_and_tester_user_roles() -> tuple[str, tuple[UserRole, ExpectedResponse]]:
    all_roles = standard_role_response()

    return (
        all_roles[0],
        [
            pytest.param(*all_roles[1][2], id="standard_user_role"),
            pytest.param(*all_roles[1][3], id="tester_user_role"),
        ],
    )


async def _new_project(
    client: TestClient,
    user_id: UserID,
    product_name: str,
    tests_data_dir: Path,
    project_data: dict[str, Any],
    as_template: bool = False,
):
    """returns a project for the given user"""
    assert client.app
    return await create_project(
        client.app,
        project_data,
        user_id,
        product_name=product_name,
        default_project_json=tests_data_dir / "fake-template-projects.isan.2dplot.json",
        as_template=as_template,
    )


def _assert_response_data(
    data: dict,
    _meta_total: PositiveInt,
    _meta_offset: PositiveInt,
    _meta_count: PositiveInt,
    _links_self: str,
    len_data: PositiveInt,
):
    assert data["_meta"]["total"] == _meta_total
    assert data["_meta"]["offset"] == _meta_offset
    assert data["_meta"]["count"] == _meta_count
    assert data["_links"]["self"].endswith(_links_self)
    assert len(data["data"]) == len_data


def _pick_random_substring(text, length):
    length = min(length, len(text))
    start_index = random.randint(0, len(text) - length)
    end_index = start_index + length
    return text[start_index:end_index]


class _ProjectInfo(BaseModel):
    uuid: ProjectID
    name: str
    description: str


@pytest.mark.parametrize(*standard_user_role())
async def test_list_projects_with_search_parameter(
    client: TestClient,
    logged_user: UserDict,
    expected: ExpectedResponse,
    fake_project: ProjectDict,
    tests_data_dir: Path,
    osparc_product_name: str,
    project_db_cleaner: None,
):
    projects_info = [
        _ProjectInfo(
            uuid="d4d0eca3-d210-4db6-84f9-63670b07176b",
            name="Name 1",
            description="Description 1",
        ),
        _ProjectInfo(
            uuid="2f3ef868-fe1b-11ed-b038-cdb13a78a6f3",
            name="Name 2",
            description="Description 2",
        ),
        _ProjectInfo(
            uuid="9cd66c12-fe1b-11ed-b038-cdb13a78a6f3",
            name="Name 3",
            description="Description 3",
        ),
        _ProjectInfo(
            uuid="b9e32426-fe1b-11ed-b038-cdb13a78a6f3",
            name="Yoda 4",
            description="Description 4",
        ),
        _ProjectInfo(
            uuid="bc57aff6-fe1b-11ed-b038-cdb13a78a6f3",
            name="Name 5",
            description="Yoda 5",
        ),
    ]

    user_projects = []
    for project_ in projects_info:
        project_data = deepcopy(fake_project)
        project_data["name"] = project_.name
        project_data["uuid"] = project_.uuid
        project_data["description"] = project_.description

        user_projects.append(
            await _new_project(
                client,
                logged_user["id"],
                osparc_product_name,
                tests_data_dir,
                project_data,
            )
        )

    # Now we will test without search parameter
    base_url = client.app.router["list_projects"].url_for()
    assert f"{base_url}" == f"/{api_version_prefix}/projects"

    resp = await client.get(f"{base_url}")
    data = await resp.json()

    assert resp.status == status.HTTP_200_OK
    _assert_response_data(data, 5, 0, 5, "/v0/projects?offset=0&limit=20", 5)

    # Now we will test with empty search parameter
    query_parameters = {"search": ""}
    url = base_url.with_query(**query_parameters)
    assert f"{url}" == f"/{api_version_prefix}/projects?search="

    resp = await client.get(f"{url}")
    data = await resp.json()

    assert resp.status == status.HTTP_200_OK
    _assert_response_data(data, 5, 0, 5, "/v0/projects?search=&offset=0&limit=20", 5)

    # Now we will test upper/lower case search
    query_parameters = {"search": "nAmE 5"}
    url = base_url.with_query(**query_parameters)
    assert f"{url}" == f"/{api_version_prefix}/projects?search=nAmE+5"

    resp = await client.get(f"{url}")
    data = await resp.json()

    assert resp.status == status.HTTP_200_OK
    _assert_response_data(
        data, 1, 0, 1, "/v0/projects?search=nAmE+5&offset=0&limit=20", 1
    )

    # Now we will test specific project name search (used by the API server)
    query_parameters = {"filters": '{"search_by_project_name": "Yoda"}'}
    url = base_url.with_query(**query_parameters)
    assert (
        f"{url}"
        == f"/{api_version_prefix}/projects?filters=%7B%22search_by_project_name%22:+%22Yoda%22%7D"
    )

    resp = await client.get(f"{url}")
    data = await resp.json()

    assert resp.status == status.HTTP_200_OK
    _assert_response_data(
        data,
        1,
        0,
        1,
        "/v0/projects?filters=%7B%22search_by_project_name%22:+%22Yoda%22%7D&offset=0&limit=20",
        1,
    )

    # Now we will test part of uuid search
    query_parameters = {"search": "2-fe1b-11ed-b038-cdb1"}
    url = base_url.with_query(**query_parameters)
    assert f"{url}" == f"/{api_version_prefix}/projects?search=2-fe1b-11ed-b038-cdb1"

    resp = await client.get(f"{url}")
    data = await resp.json()

    assert resp.status == status.HTTP_200_OK
    _assert_response_data(
        data, 1, 0, 1, "/v0/projects?search=2-fe1b-11ed-b038-cdb1&offset=0&limit=20", 1
    )

    # Now we will test part of prjOwner search
    user_name_ = logged_user["name"]
    user_name_substring = _pick_random_substring(user_name_, 5)
    query_parameters = {"search": user_name_substring}
    url = base_url.with_query(**query_parameters)
    user_name_substring_query_parsed = user_name_substring.replace(" ", "+")
    assert (
        f"{url}"
        == f"/{api_version_prefix}/projects?search={user_name_substring_query_parsed}"
    )

    resp = await client.get(f"{url}")
    data = await resp.json()

    assert resp.status == status.HTTP_200_OK
    _assert_response_data(
        data,
        5,
        0,
        5,
        f"/v0/projects?search={user_name_substring_query_parsed}&offset=0&limit=20",
        5,
    )

    # Now we will test search that contains the substring in more columns
    query_parameters = {"search": "oda"}
    url = base_url.with_query(**query_parameters)
    assert f"{url}" == f"/{api_version_prefix}/projects?search=oda"

    resp = await client.get(f"{url}")
    data = await resp.json()

    assert resp.status == status.HTTP_200_OK
    _assert_response_data(data, 2, 0, 2, "/v0/projects?search=oda&offset=0&limit=20", 2)

    # Now we will test search that returns nothing
    query_parameters = {"search": "does not exists"}
    url = base_url.with_query(**query_parameters)
    assert f"{url}" == f"/{api_version_prefix}/projects?search=does+not+exists"

    resp = await client.get(f"{url}")
    data = await resp.json()

    assert resp.status == status.HTTP_200_OK
    _assert_response_data(
        data, 0, 0, 0, "/v0/projects?search=does+not+exists&offset=0&limit=20", 0
    )

    # Now we will test search with offset parameters
    query_parameters = {"search": "oda", "offset": "0", "limit": "1"}
    url = base_url.with_query(**query_parameters)
    assert f"{url}" == f"/{api_version_prefix}/projects?search=oda&offset=0&limit=1"

    resp = await client.get(f"{url}")
    data = await resp.json()

    assert resp.status == status.HTTP_200_OK
    _assert_response_data(data, 2, 0, 1, "/v0/projects?search=oda&offset=0&limit=1", 1)
    assert data["_meta"]["limit"] == 1
    assert data["_links"]["next"].endswith("/v0/projects?search=oda&offset=1&limit=1")
    assert data["_links"]["last"].endswith("/v0/projects?search=oda&offset=1&limit=1")


_alphabetically_ordered_list = ["a", "b", "c", "d", "e"]


@pytest.mark.parametrize(*standard_user_role())
async def test_list_projects_with_order_by_parameter(
    client: TestClient,
    logged_user: UserDict,
    expected: ExpectedResponse,
    fake_project: ProjectDict,
    tests_data_dir: Path,
    osparc_product_name: str,
    project_db_cleaner: None,
):
    projects_info = [
        _ProjectInfo(
            uuid="aaa0eca3-d210-4db6-84f9-63670b07176b",
            name="d",
            description="c",
        ),
        _ProjectInfo(
            uuid="cccef868-fe1b-11ed-b038-cdb13a78a6f3",
            name="b",
            description="e",
        ),
        _ProjectInfo(
            uuid="eee66c12-fe1b-11ed-b038-cdb13a78a6f3",
            name="a",
            description="a",
        ),
        _ProjectInfo(
            uuid="ddd32426-fe1b-11ed-b038-cdb13a78a6f3",
            name="c",
            description="b",
        ),
        _ProjectInfo(
            uuid="bbb7aff6-fe1b-11ed-b038-cdb13a78a6f3",
            name="e",
            description="d",
        ),
    ]

    user_projects = []
    for project_ in projects_info:
        project_data = deepcopy(fake_project)
        project_data["name"] = project_.name
        project_data["uuid"] = project_.uuid
        project_data["description"] = project_.description

        user_projects.append(
            await _new_project(
                client,
                logged_user["id"],
                osparc_product_name,
                tests_data_dir,
                project_data,
            )
        )

    # Order by uuid ascending
    base_url = client.app.router["list_projects"].url_for()
    url = base_url.with_query(
        order_by=json.dumps({"field": "uuid", "direction": "asc"})
    )
    assert (
        f"{url}"
        == f"/{api_version_prefix}/projects?order_by=%7B%22field%22:+%22uuid%22,+%22direction%22:+%22asc%22%7D"
    )
    resp = await client.get(f"{url}")
    data = await resp.json()
    assert resp.status == status.HTTP_200_OK
    assert [item["uuid"][0] for item in data["data"]] == _alphabetically_ordered_list

    # Order by uuid descending
    base_url = client.app.router["list_projects"].url_for()
    url = base_url.with_query(
        order_by=json.dumps({"field": "uuid", "direction": "desc"})
    )
    resp = await client.get(f"{url}")
    data = await resp.json()
    assert resp.status == status.HTTP_200_OK
    assert [item["uuid"][0] for item in data["data"]] == _alphabetically_ordered_list[
        ::-1
    ]

    # Order by name ascending
    base_url = client.app.router["list_projects"].url_for()
    url = base_url.with_query(
        order_by=json.dumps({"field": "name", "direction": "asc"})
    )
    resp = await client.get(f"{url}")
    data = await resp.json()
    assert resp.status == status.HTTP_200_OK
    assert [item["name"][0] for item in data["data"]] == _alphabetically_ordered_list

    # Order by description ascending
    base_url = client.app.router["list_projects"].url_for()
    url = base_url.with_query(
        order_by=json.dumps({"field": "description", "direction": "asc"})
    )
    resp = await client.get(f"{url}")
    data = await resp.json()
    assert resp.status == status.HTTP_200_OK
    assert [
        item["description"][0] for item in data["data"]
    ] == _alphabetically_ordered_list


@pytest.fixture()
def setup_folders_db(
    postgres_db: sa.engine.Engine,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
) -> Iterator[FolderID]:
    with postgres_db.connect() as con:
        result = con.execute(
            folders_v2.insert()
            .values(
                name="My Folder 1",
                parent_folder_id=None,
                user_id=logged_user["id"],
                workspace_id=None,
                product_name="osparc",
                created_by_gid=logged_user["primary_gid"],
            )
            .returning(folders_v2.c.folder_id)
        )
        _folder_id = result.fetchone()[0]

        con.execute(
            projects_to_folders.insert().values(
                folder_id=_folder_id,
                project_uuid=user_project["uuid"],
                user_id=logged_user["id"],
            )
        )

        yield FolderID(_folder_id)

        con.execute(projects_to_folders.delete())
        con.execute(folders_v2.delete())


@pytest.mark.parametrize(*standard_user_role())
async def test_list_projects_for_specific_folder_id(
    client: TestClient,
    logged_user: UserDict,
    expected: ExpectedResponse,
    fake_project: ProjectDict,
    tests_data_dir: Path,
    osparc_product_name: str,
    project_db_cleaner: None,
    setup_folders_db: FolderID,
):
    projects_info = [
        _ProjectInfo(
            uuid="d4d0eca3-d210-4db6-84f9-63670b07176b",
            name="Name 1",
            description="Description 1",
        ),
        _ProjectInfo(
            uuid="2f3ef868-fe1b-11ed-b038-cdb13a78a6f3",
            name="Name 2",
            description="Description 2",
        ),
        _ProjectInfo(
            uuid="9cd66c12-fe1b-11ed-b038-cdb13a78a6f3",
            name="Name 3",
            description="Description 3",
        ),
    ]

    user_projects = []
    for project_ in projects_info:
        project_data = deepcopy(fake_project)
        project_data["name"] = project_.name
        project_data["uuid"] = project_.uuid
        project_data["description"] = project_.description

        user_projects.append(
            await _new_project(
                client,
                logged_user["id"],
                osparc_product_name,
                tests_data_dir,
                project_data,
            )
        )

    # Now we will test listing of the root directory
    base_url = client.app.router["list_projects"].url_for()
    assert f"{base_url}" == f"/{api_version_prefix}/projects"

    resp = await client.get(f"{base_url}")
    data = await resp.json()

    assert resp.status == status.HTTP_200_OK
    _assert_response_data(data, 3, 0, 3, "/v0/projects?offset=0&limit=20", 3)

    # Now we will test listing of the root directory with provided folder id query
    query_parameters = {"folder_id": "null"}
    url = base_url.with_query(**query_parameters)

    resp = await client.get(f"{url}")
    data = await resp.json()

    assert resp.status == status.HTTP_200_OK
    _assert_response_data(
        data, 3, 0, 3, "/v0/projects?folder_id=null&offset=0&limit=20", 3
    )

    # Now we will test listing for specific folder
    query_parameters = {"folder_id": f"{setup_folders_db}"}
    url = base_url.with_query(**query_parameters)
    assert f"{url}" == f"/{api_version_prefix}/projects?folder_id={setup_folders_db}"

    resp = await client.get(f"{url}")
    data = await resp.json()

    assert resp.status == status.HTTP_200_OK
    _assert_response_data(
        data, 1, 0, 1, f"/v0/projects?folder_id={setup_folders_db}&offset=0&limit=20", 1
    )


@pytest.mark.parametrize(*standard_and_tester_user_roles())
async def test_list_and_patch_projects_with_template_type(
    client: TestClient,
    logged_user: UserDict,
    expected: ExpectedResponse,
    fake_project: ProjectDict,
    tests_data_dir: Path,
    osparc_product_name: str,
    project_db_cleaner: None,
):
    projects_type = [
        "STANDARD",
        "STANDARD",
        "STANDARD",
        "TEMPLATE",
        "TEMPLATE",
    ]
    generated_projects = []
    for _type in projects_type:
        project_data = deepcopy(fake_project)
        prj = await _new_project(
            client,
            logged_user["id"],
            osparc_product_name,
            tests_data_dir,
            project_data,
            as_template=_type == "TEMPLATE",
        )
        generated_projects.append(prj)

    base_url = client.app.router["list_projects"].url_for()
    # Now we will test listing with type=user
    query_parameters = {"type": "user"}
    url = base_url.with_query(**query_parameters)

    resp = await client.get(f"{url}")
    data = await resp.json()

    assert resp.status == status.HTTP_200_OK
    _assert_response_data(data, 3, 0, 3, "/v0/projects?type=user&offset=0&limit=20", 3)

    # Now we will test listing with type=all
    query_parameters = {"type": "all"}
    url = base_url.with_query(**query_parameters)

    resp = await client.get(f"{url}")
    data = await resp.json()

    assert resp.status == status.HTTP_200_OK
    _assert_response_data(data, 5, 0, 5, "/v0/projects?type=all&offset=0&limit=20", 5)

    # Now we will test listing with type=template
    query_parameters = {"type": "template"}
    url = base_url.with_query(**query_parameters)

    resp = await client.get(f"{url}")
    data = await resp.json()

    assert resp.status == status.HTTP_200_OK
    _assert_response_data(
        data, 2, 0, 2, "/v0/projects?type=template&offset=0&limit=20", 2
    )

    # Now we will test listing with type=user and template_type=null
    query_parameters = {"type": "user", "template_type": "null"}
    url = base_url.with_query(**query_parameters)

    resp = await client.get(f"{url}")
    data = await resp.json()

    assert resp.status == status.HTTP_200_OK
    _assert_response_data(
        data, 3, 0, 3, "/v0/projects?type=user&template_type=null&offset=0&limit=20", 3
    )

    # Now we will test listing with incompatible type and template_type
    query_parameters = {"type": "user", "template_type": "TEMPLATE"}
    url = base_url.with_query(**query_parameters)
    resp = await client.get(f"{url}")
    data = await resp.json()
    assert resp.status == 422

    # Now we will test listing with type=template and template_type=TEMPLATE
    query_parameters = {"type": "template", "template_type": "TEMPLATE"}
    url = base_url.with_query(**query_parameters)

    resp = await client.get(f"{url}")
    data = await resp.json()

    assert resp.status == status.HTTP_200_OK
    _assert_response_data(
        data,
        2,
        0,
        2,
        "/v0/projects?type=template&template_type=TEMPLATE&offset=0&limit=20",
        2,
    )

    # Lets now PATCH the template project (Currently user is not tester so it should fail)
    patch_url = client.app.router["patch_project"].url_for(
        project_id=generated_projects[-1]["uuid"]  # <-- Patching template project
    )
    resp = await client.patch(
        f"{patch_url}",
        data=json.dumps(
            {
                "templateType": ProjectTemplateType.HYPERTOOL.value,
            }
        ),
    )
    if UserRole(logged_user["role"]) >= UserRole.TESTER:
        await assert_status(resp, status.HTTP_204_NO_CONTENT)
    else:
        await assert_status(resp, status.HTTP_403_FORBIDDEN)

    if UserRole(logged_user["role"]) >= UserRole.TESTER:
        # Now we will test listing with type=user and template_type=null
        query_parameters = {"type": "user", "template_type": "null"}
        url = base_url.with_query(**query_parameters)

        resp = await client.get(f"{url}")
        data = await resp.json()

        assert resp.status == status.HTTP_200_OK
        _assert_response_data(
            data,
            3,
            0,
            3,
            "/v0/projects?type=user&template_type=null&offset=0&limit=20",
            3,
        )

        # Now we will test listing with type=user and template_type=HYPERTOOL
        query_parameters = {"type": "template", "template_type": "HYPERTOOL"}
        url = base_url.with_query(**query_parameters)

        resp = await client.get(f"{url}")
        data = await resp.json()

        assert resp.status == status.HTTP_200_OK
        _assert_response_data(
            data,
            1,
            0,
            1,
            "/v0/projects?type=template&template_type=HYPERTOOL&offset=0&limit=20",
            1,
        )

        # Now we will test listing with type=template and template_type=TEMPLATE
        query_parameters = {"type": "template", "template_type": "TEMPLATE"}
        url = base_url.with_query(**query_parameters)

        resp = await client.get(f"{url}")
        data = await resp.json()

        assert resp.status == status.HTTP_200_OK
        _assert_response_data(
            data,
            1,
            0,
            1,
            "/v0/projects?type=template&template_type=TEMPLATE&offset=0&limit=20",
            1,
        )

        # Lets now PATCH the standard project
        patch_url = client.app.router["patch_project"].url_for(
            project_id=generated_projects[0]["uuid"]  # <-- Patching standard project
        )
        resp = await client.patch(
            f"{patch_url}",
            data=json.dumps(
                {
                    "templateType": ProjectTemplateType.HYPERTOOL.value,
                }
            ),
        )
        await assert_status(resp, status.HTTP_400_BAD_REQUEST)
