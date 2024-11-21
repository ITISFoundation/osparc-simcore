# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import re
import uuid as uuidlib
from collections.abc import Awaitable, Callable, Iterator
from http import HTTPStatus
from math import ceil
from typing import Any

import pytest
import sqlalchemy as sa
from aiohttp.test_utils import TestClient
from aioresponses import aioresponses
from faker import Faker
from models_library.products import ProductName
from models_library.projects_state import ProjectState
from pydantic import TypeAdapter
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.webserver_login import UserInfoDict
from pytest_simcore.helpers.webserver_parametrizations import (
    ExpectedResponse,
    MockedStorageSubsystem,
    standard_role_response,
    standard_user_role_response,
)
from servicelib.aiohttp import status
from servicelib.rest_constants import X_PRODUCT_NAME_HEADER
from simcore_postgres_database.models.products import products
from simcore_postgres_database.models.projects_to_products import projects_to_products
from simcore_service_webserver._meta import api_version_prefix
from simcore_service_webserver.db.models import UserRole
from simcore_service_webserver.groups.api import (
    auto_add_user_to_product_group,
    get_product_group_for_user,
)
from simcore_service_webserver.groups.exceptions import GroupNotFoundError
from simcore_service_webserver.products.api import get_product
from simcore_service_webserver.projects._permalink_api import ProjectPermalink
from simcore_service_webserver.projects.models import ProjectDict
from simcore_service_webserver.utils import to_datetime
from yarl import URL

API_PREFIX = "/" + api_version_prefix


def assert_replaced(current_project, update_data):
    def _extract(dikt, keys):
        return {k: dikt[k] for k in keys}

    modified = [
        "lastChangeDate",
    ]
    keep = [k for k in update_data if k not in modified]

    assert _extract(current_project, keep) == _extract(update_data, keep)

    k = "lastChangeDate"
    assert to_datetime(update_data[k]) < to_datetime(current_project[k])


async def _list_and_assert_projects(
    client: TestClient,
    expected: HTTPStatus,
    query_parameters: dict | None = None,
    headers: dict | None = None,
    expected_error_msg: str | None = None,
    expected_error_code: str | None = None,
) -> tuple[list[ProjectDict], dict[str, Any], dict[str, Any]]:
    if not query_parameters:
        query_parameters = {}

    # GET /v0/projects
    assert client.app
    url = client.app.router["list_projects"].url_for()
    assert str(url) == API_PREFIX + "/projects"
    if query_parameters:
        url = url.with_query(**query_parameters)

    if headers is None:
        headers = {}

    resp = await client.get(f"{url}", headers=headers)
    data, errors, meta, links = await assert_status(
        resp,
        expected,
        expected_msg=expected_error_msg,
        expected_error_code=expected_error_code,
        include_meta=True,
        include_links=True,
    )
    if data is not None:
        assert errors is None
        assert meta is not None
        assert isinstance(data, list)

        # see [api/specs/webserver/openapi-projects.yaml] for defaults
        exp_offset = max(int(query_parameters.get("offset", 0)), 0)
        exp_limit = max(1, min(int(query_parameters.get("limit", 20)), 50))
        assert meta["offset"] == exp_offset
        assert meta["limit"] == exp_limit
        exp_last_page = ceil(meta["total"] / meta["limit"] - 1)
        assert links is not None
        complete_url = client.make_url(f"{url}")
        assert links["self"] == str(
            URL(complete_url).update_query({"offset": exp_offset, "limit": exp_limit})
        )
        assert links["first"] == str(
            URL(complete_url).update_query({"offset": 0, "limit": exp_limit})
        )
        assert links["last"] == str(
            URL(complete_url).update_query(
                {"offset": exp_last_page * exp_limit, "limit": exp_limit}
            )
        )
        if exp_offset <= 0:
            assert links["prev"] is None
        else:
            assert links["prev"] == str(
                URL(complete_url).update_query(
                    {"offset": max(exp_offset - exp_limit, 0), "limit": exp_limit}
                )
            )
        if exp_offset >= (exp_last_page * exp_limit):
            assert links["next"] is None
        else:
            assert links["next"] == str(
                URL(complete_url).update_query(
                    {
                        "offset": min(
                            exp_offset + exp_limit, exp_last_page * exp_limit
                        ),
                        "limit": exp_limit,
                    }
                )
            )
    else:
        assert meta is None
        assert links is None
        assert errors is not None

    return data, meta, links


async def _assert_get_same_project(
    client: TestClient,
    project: dict,
    expected: HTTPStatus,
) -> None:
    # GET /v0/projects/{project_id}

    # with a project owned by user
    assert client.app
    url = client.app.router["get_project"].url_for(project_id=project["uuid"])
    assert str(url) == f"{API_PREFIX}/projects/{project['uuid']}"
    resp = await client.get(f"{url}")
    data, error = await assert_status(resp, expected)

    if not error:
        # Optional fields are not part of reference 'project'
        project_state = data.pop("state")
        project_permalink = data.pop("permalink", None)
        folder_id = data.pop("folderId", None)

        assert data == {k: project[k] for k in data}

        if project_state:
            assert ProjectState.model_validate(project_state)

        if project_permalink:
            assert ProjectPermalink.model_validate(project_permalink)

        assert folder_id is None


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.ANONYMOUS, status.HTTP_401_UNAUTHORIZED),
        (UserRole.GUEST, status.HTTP_200_OK),
        (UserRole.USER, status.HTTP_200_OK),
        (UserRole.TESTER, status.HTTP_200_OK),
    ],
)
async def test_list_projects(
    client: TestClient,
    logged_user: dict[str, Any],
    user_project: dict[str, Any],
    template_project: dict[str, Any],
    expected: HTTPStatus,
    catalog_subsystem_mock: Callable[[list[ProjectDict]], None],
    director_v2_service_mock: aioresponses,
):
    catalog_subsystem_mock([user_project, template_project])
    data, *_ = await _list_and_assert_projects(client, expected)

    if data:
        assert len(data) == 2

        # template project
        got = data[0]
        project_state = got.pop("state")
        project_permalink = got.pop("permalink")
        folder_id = got.pop("folderId")

        assert got == {k: template_project[k] for k in got}
        assert not ProjectState(
            **project_state
        ).locked.value, "Templates are not locked"
        assert ProjectPermalink.model_validate(project_permalink)

        # standard project
        got = data[1]
        project_state = got.pop("state")
        project_permalink = got.pop("permalink", None)
        folder_id = got.pop("folderId")

        assert got == {k: user_project[k] for k in got}
        assert ProjectState(**project_state)
        assert project_permalink is None
        assert folder_id is None

    # GET /v0/projects?type=user
    data, *_ = await _list_and_assert_projects(client, expected, {"type": "user"})
    if data:
        assert len(data) == 1

        # standad project
        got = data[0]
        project_state = got.pop("state")
        project_permalink = got.pop("permalink", None)
        folder_id = got.pop("folderId")

        assert got == {k: user_project[k] for k in got}
        assert not ProjectState(
            **project_state
        ).locked.value, "Single user does not lock"
        assert project_permalink is None

    # GET /v0/projects?type=template
    # instead /v0/projects/templates ??
    data, *_ = await _list_and_assert_projects(client, expected, {"type": "template"})
    if data:
        assert len(data) == 1

        # template project
        got = data[0]
        project_state = got.pop("state")
        project_permalink = got.pop("permalink")
        folder_id = got.pop("folderId")

        assert got == {k: template_project[k] for k in got}
        assert not ProjectState(
            **project_state
        ).locked.value, "Templates are not locked"
        assert ProjectPermalink.model_validate(project_permalink)


@pytest.fixture(scope="session")
def s4l_product_name() -> ProductName:
    return "s4l"


@pytest.fixture
def s4l_products_db_name(
    postgres_db: sa.engine.Engine, s4l_product_name: ProductName
) -> Iterator[str]:
    with postgres_db.connect() as conn:
        conn.execute(
            products.insert().values(
                name=s4l_product_name, host_regex="pytest", display_name="pytest"
            )
        )

    yield s4l_product_name

    with postgres_db.connect() as conn:
        conn.execute(products.delete().where(products.c.name == s4l_product_name))


@pytest.fixture
def s4l_product_headers(s4l_products_db_name: ProductName) -> dict[str, str]:
    return {X_PRODUCT_NAME_HEADER: s4l_products_db_name}


@pytest.fixture
async def logged_user_registed_in_two_products(
    client: TestClient, logged_user: UserInfoDict, s4l_products_db_name: ProductName
):
    assert client.app
    # registered to osparc
    osparc_product = get_product(client.app, "osparc")
    assert osparc_product.group_id
    assert await get_product_group_for_user(
        client.app, user_id=logged_user["id"], product_gid=osparc_product.group_id
    )

    # not registered to s4l
    s4l_product = get_product(client.app, s4l_products_db_name)
    assert s4l_product.group_id

    with pytest.raises(GroupNotFoundError):
        await get_product_group_for_user(
            client.app, user_id=logged_user["id"], product_gid=s4l_product.group_id
        )

    # register
    await auto_add_user_to_product_group(
        client.app, user_id=logged_user["id"], product_name=s4l_products_db_name
    )

    assert await get_product_group_for_user(
        client.app, user_id=logged_user["id"], product_gid=s4l_product.group_id
    )


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.USER, status.HTTP_200_OK),
    ],
)
async def test_list_projects_with_innaccessible_services(
    s4l_products_db_name: ProductName,
    client: TestClient,
    logged_user_registed_in_two_products: UserInfoDict,
    user_project: dict[str, Any],
    template_project: dict[str, Any],
    expected: HTTPStatus,
    catalog_subsystem_mock: Callable[[list[ProjectDict]], None],
    director_v2_service_mock: aioresponses,
    postgres_db: sa.engine.Engine,
    s4l_product_headers: dict[str, Any],
):
    # use-case 1: calling with correct product name returns 2 projects
    # projects are linked to osparc
    data, *_ = await _list_and_assert_projects(client, expected)
    assert len(data) == 2

    # use-case 2: calling with another product name returns 0 projects
    # because projects are linked to osparc product in projects_to_products table
    data, *_ = await _list_and_assert_projects(
        client, expected, headers=s4l_product_headers
    )
    assert len(data) == 0

    # use-case 3: remove the links to products
    # shall still return 0 because the user has no access to the services
    with postgres_db.connect() as conn:
        conn.execute(projects_to_products.delete())
    data, *_ = await _list_and_assert_projects(
        client, expected, headers=s4l_product_headers
    )
    assert len(data) == 0
    data, *_ = await _list_and_assert_projects(client, expected)
    assert len(data) == 0

    # use-case 4: give user access to services
    # shall return the projects for any product
    catalog_subsystem_mock([user_project, template_project])
    data, *_ = await _list_and_assert_projects(
        client, expected, headers=s4l_product_headers
    )
    # UPDATE (use-case 4): 11.11.2024 - This test was checking backwards compatibility for listing
    # projects that were not in the projects_to_products table. After refactoring the project listing,
    # we no longer support this. MD double-checked the last_modified_timestamp on projects
    # that do not have any product assigned (all of them were before 01-11-2022 with the exception of two
    # `4b001ad2-8450-11ec-b105-02420a0b02c7` and `d952cbf4-d838-11ec-af92-02420a0bdad4` which were added to osparc product).
    assert len(data) == 0
    data, *_ = await _list_and_assert_projects(client, expected)
    assert len(data) == 0


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.ANONYMOUS, status.HTTP_401_UNAUTHORIZED),
        (UserRole.GUEST, status.HTTP_200_OK),
        (UserRole.USER, status.HTTP_200_OK),
        (UserRole.TESTER, status.HTTP_200_OK),
    ],
)
async def test_get_project(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    template_project: ProjectDict,
    expected,
    catalog_subsystem_mock: Callable[[list[ProjectDict]], None],
):
    catalog_subsystem_mock([user_project, template_project])

    # standard project
    await _assert_get_same_project(client, user_project, expected)

    # with a template
    await _assert_get_same_project(client, template_project, expected)


# POST --------


@pytest.mark.parametrize(*standard_role_response())
async def test_new_project(
    client: TestClient,
    logged_user: UserInfoDict,
    primary_group,
    expected: ExpectedResponse,
    storage_subsystem_mock,
    project_db_cleaner,
    request_create_project: Callable[..., Awaitable[ProjectDict]],
):
    await request_create_project(
        client, expected.accepted, expected.created, logged_user, primary_group
    )


@pytest.mark.parametrize(*standard_user_role_response())
async def test_new_project_from_template(
    client: TestClient,
    logged_user: UserInfoDict,
    primary_group: dict[str, str],
    template_project,
    expected: ExpectedResponse,
    storage_subsystem_mock,
    project_db_cleaner,
    request_create_project: Callable[..., Awaitable[ProjectDict]],
):
    new_project = await request_create_project(
        client,
        expected.accepted,
        expected.created,
        logged_user,
        primary_group,
        from_study=template_project,
    )

    if new_project:
        # check uuid replacement
        for node_name in new_project["workbench"]:
            TypeAdapter(uuidlib.UUID).validate_python(node_name)


@pytest.mark.parametrize(*standard_user_role_response())
async def test_new_project_from_other_study(
    client: TestClient,
    logged_user: UserInfoDict,
    primary_group: dict[str, str],
    user_project: ProjectDict,
    expected: ExpectedResponse,
    storage_subsystem_mock,
    catalog_subsystem_mock: Callable[[list[ProjectDict]], None],
    project_db_cleaner,
    request_create_project: Callable[..., Awaitable[ProjectDict]],
):
    catalog_subsystem_mock([user_project])
    new_project = await request_create_project(
        client,
        expected.accepted,
        expected.created,
        logged_user,
        primary_group,
        from_study=user_project,
    )

    if new_project:
        # check uuid replacement
        assert new_project["name"].endswith("(Copy)")
        for node_name in new_project["workbench"]:
            TypeAdapter(uuidlib.UUID).validate_python(node_name)


@pytest.mark.parametrize(*standard_user_role_response())
async def test_new_project_from_template_with_body(
    client: TestClient,
    logged_user: UserInfoDict,
    primary_group: dict[str, str],
    standard_groups: list[dict[str, str]],
    template_project,
    expected: ExpectedResponse,
    storage_subsystem_mock,
    project_db_cleaner,
    request_create_project: Callable[..., Awaitable[ProjectDict]],
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
    project = await request_create_project(
        client,
        expected.accepted,
        expected.created,
        logged_user,
        primary_group,
        project=predefined,
        from_study=template_project,
    )

    if project:
        # uses predefined
        assert project["name"] == predefined["name"]
        assert project["description"] == predefined["description"]

        # different uuids for project and nodes!?
        assert project["uuid"] != template_project["uuid"]

        # check uuid replacement
        for node_name in project["workbench"]:
            TypeAdapter(uuidlib.UUID).validate_python(node_name)


@pytest.mark.parametrize(*standard_user_role_response())
async def test_new_template_from_project(
    client: TestClient,
    logged_user: dict[str, Any],
    primary_group: dict[str, str],
    all_group: dict[str, str],
    user_project: dict[str, Any],
    expected: ExpectedResponse,
    storage_subsystem_mock: MockedStorageSubsystem,
    catalog_subsystem_mock: Callable[[list[ProjectDict]], None],
    project_db_cleaner: None,
    request_create_project: Callable[..., Awaitable[ProjectDict]],
):
    assert client.app
    new_template_prj = await request_create_project(
        client,
        expected.accepted,
        expected.created,
        logged_user,
        primary_group,
        from_study=user_project,
        as_template=True,
    )

    if new_template_prj:
        template_project = new_template_prj
        catalog_subsystem_mock([template_project])

        templates, *_ = await _list_and_assert_projects(
            client, status.HTTP_200_OK, {"type": "template"}
        )

        assert len(templates) == 1
        assert templates[0] == template_project

        assert template_project["name"] == user_project["name"]
        assert template_project["description"] == user_project["description"]
        assert template_project["prjOwner"] == logged_user["email"]
        assert template_project["accessRights"] == user_project["accessRights"]

        # different timestamps
        assert to_datetime(user_project["creationDate"]) < to_datetime(
            template_project["creationDate"]
        )
        assert to_datetime(user_project["lastChangeDate"]) < to_datetime(
            template_project["lastChangeDate"]
        )

        # different uuids for project and nodes!?
        assert template_project["uuid"] != user_project["uuid"]

        # check uuid replacement
        for node_name in template_project["workbench"]:
            TypeAdapter(uuidlib.UUID).validate_python(node_name)

    # do the same with a body
    predefined = {
        "uuid": "",
        "name": "My super duper new template",
        "description": "Some lines from user",
        "thumbnail": "",
        "prjOwner": "",
        "creationDate": "2019-06-03T09:59:31.987Z",
        "lastChangeDate": "2019-06-03T09:59:31.987Z",
        "workbench": {},
        "accessRights": {
            str(all_group["gid"]): {"read": True, "write": False, "delete": False},
        },
        "tags": [],
        "classifiers": [],
        "workspaceId": None,
    }
    new_template_prj = await request_create_project(
        client,
        expected.accepted,
        expected.created,
        logged_user,
        primary_group,
        project=predefined,
        from_study=user_project,
        as_template=True,
    )

    if new_template_prj:
        template_project = new_template_prj

        # uses predefined
        assert template_project["name"] == predefined["name"]
        assert template_project["description"] == predefined["description"]
        assert template_project["prjOwner"] == logged_user["email"]
        # the logged in user access rights are added by default
        predefined["accessRights"].update(
            {str(primary_group["gid"]): {"read": True, "write": True, "delete": True}}
        )
        assert template_project["accessRights"] == predefined["accessRights"]

        # different ownership
        assert template_project["prjOwner"] == logged_user["email"]
        assert template_project["prjOwner"] == user_project["prjOwner"]

        # different timestamps
        assert to_datetime(user_project["creationDate"]) < to_datetime(
            template_project["creationDate"]
        )
        assert to_datetime(user_project["lastChangeDate"]) < to_datetime(
            template_project["lastChangeDate"]
        )

        # different uuids for project and nodes!?
        assert template_project["uuid"] != user_project["uuid"]

        # check uuid replacement
        for node_name in template_project["workbench"]:
            TypeAdapter(uuidlib.UUID).validate_python(node_name)


@pytest.fixture
def mock_director_v2_inactivity(
    aioresponses_mocker: aioresponses, is_inactive: bool
) -> None:
    aioresponses_mocker.clear()
    get_services_pattern = re.compile(
        r"^http://[a-z\-_]*director-v2:[0-9]+/v2/dynamic_services/projects/.*/inactivity.*$"
    )
    aioresponses_mocker.get(
        get_services_pattern,
        status=status.HTTP_200_OK,
        repeat=True,
        payload={"is_inactive": is_inactive},
    )


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.ANONYMOUS, status.HTTP_401_UNAUTHORIZED),
        *((role, status.HTTP_200_OK) for role in UserRole if role > UserRole.ANONYMOUS),
    ],
)
@pytest.mark.parametrize("is_inactive", [True, False])
async def test_get_project_inactivity(
    mock_director_v2_inactivity: None,
    logged_user: UserInfoDict,
    client: TestClient,
    faker: Faker,
    user_role: UserRole,
    expected: HTTPStatus,
    is_inactive: bool,
):
    mock_project_id = faker.uuid4()

    assert client.app
    url = client.app.router["get_project_inactivity"].url_for(
        project_id=mock_project_id
    )
    assert f"/v0/projects/{mock_project_id}/inactivity" == url.path
    response = await client.get(f"{url}")
    data, error = await assert_status(response, expected)
    if user_role == UserRole.ANONYMOUS:
        return

    assert data
    assert error is None
    assert data["is_inactive"] is is_inactive
