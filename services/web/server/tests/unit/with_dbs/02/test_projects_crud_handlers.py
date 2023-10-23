# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import random
import re
import uuid as uuidlib
from collections.abc import Awaitable, Callable, Iterator
from copy import deepcopy
from math import ceil
from typing import Any

import pytest
import sqlalchemy as sa
from aiohttp import web
from aiohttp.test_utils import TestClient
from aioresponses import aioresponses
from faker import Faker
from models_library.projects_nodes import Node
from models_library.projects_state import ProjectState
from models_library.services import ServiceKey
from models_library.utils.fastapi_encoders import jsonable_encoder
from pydantic import parse_obj_as
from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_login import UserInfoDict
from pytest_simcore.helpers.utils_webserver_unit_with_db import (
    ExpectedResponse,
    MockedStorageSubsystem,
    standard_role_response,
)
from simcore_postgres_database.models.products import products
from simcore_postgres_database.models.projects_to_products import projects_to_products
from simcore_service_webserver._constants import X_PRODUCT_NAME_HEADER
from simcore_service_webserver._meta import api_version_prefix
from simcore_service_webserver.db.models import UserRole
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


async def _list_projects(
    client: TestClient,
    expected: type[web.HTTPException],
    query_parameters: dict | None = None,
    headers: dict | None = None,
    expected_error_msg: str | None = None,
    expected_error_code: str | None = None,
) -> tuple[list[dict], dict[str, Any], dict[str, Any]]:
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
        assert meta is not None
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
    return data, meta, links


async def _assert_get_same_project(
    client: TestClient,
    project: dict,
    expected: type[web.HTTPException],
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

        assert data == project

        if project_state:
            assert parse_obj_as(ProjectState, project_state)

        if project_permalink:
            assert parse_obj_as(ProjectPermalink, project_permalink)


async def _replace_project(
    client: TestClient, project_update: dict, expected: type[web.HTTPException]
) -> dict:
    assert client.app

    # PUT /v0/projects/{project_id}
    url = client.app.router["replace_project"].url_for(
        project_id=project_update["uuid"]
    )
    assert str(url) == f"{API_PREFIX}/projects/{project_update['uuid']}"
    resp = await client.put(f"{url}", json=project_update)
    data, error = await assert_status(resp, expected)
    if not error:
        assert_replaced(current_project=data, update_data=project_update)
    return data


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.ANONYMOUS, web.HTTPUnauthorized),
        (UserRole.GUEST, web.HTTPOk),
        (UserRole.USER, web.HTTPOk),
        (UserRole.TESTER, web.HTTPOk),
    ],
)
async def test_list_projects(
    client: TestClient,
    logged_user: dict[str, Any],
    user_project: dict[str, Any],
    template_project: dict[str, Any],
    expected: type[web.HTTPException],
    catalog_subsystem_mock: Callable[[list[ProjectDict]], None],
    director_v2_service_mock: aioresponses,
):
    catalog_subsystem_mock([user_project, template_project])
    data, *_ = await _list_projects(client, expected)

    if data:
        assert len(data) == 2

        # template project
        project_state = data[0].pop("state")
        project_permalink = data[0].pop("permalink")

        assert data[0] == template_project
        assert not ProjectState(
            **project_state
        ).locked.value, "Templates are not locked"
        assert parse_obj_as(ProjectPermalink, project_permalink)

        # standard project
        project_state = data[1].pop("state")
        project_permalink = data[1].pop("permalink", None)

        assert data[1] == user_project
        assert ProjectState(**project_state)
        assert project_permalink is None

    # GET /v0/projects?type=user
    data, *_ = await _list_projects(client, expected, {"type": "user"})
    if data:
        assert len(data) == 1

        # standad project
        project_state = data[0].pop("state")
        project_permalink = data[0].pop("permalink", None)

        assert data[0] == user_project
        assert not ProjectState(
            **project_state
        ).locked.value, "Single user does not lock"
        assert project_permalink is None

    # GET /v0/projects?type=template
    # instead /v0/projects/templates ??
    data, *_ = await _list_projects(client, expected, {"type": "template"})
    if data:
        assert len(data) == 1

        # template project
        project_state = data[0].pop("state")
        project_permalink = data[0].pop("permalink")

        assert data[0] == template_project
        assert not ProjectState(
            **project_state
        ).locked.value, "Templates are not locked"
        assert parse_obj_as(ProjectPermalink, project_permalink)


@pytest.fixture(scope="session")
def s4l_product_name() -> str:
    return "s4l"


@pytest.fixture
def s4l_products_db_name(
    postgres_db: sa.engine.Engine, s4l_product_name: str
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
def s4l_product_headers(s4l_products_db_name: str) -> dict[str, str]:
    return {X_PRODUCT_NAME_HEADER: s4l_products_db_name}


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.USER, web.HTTPOk),
    ],
)
async def test_list_projects_with_innaccessible_services(
    s4l_products_db_name: str,
    client: TestClient,
    logged_user: dict[str, Any],
    user_project: dict[str, Any],
    template_project: dict[str, Any],
    expected: type[web.HTTPException],
    catalog_subsystem_mock: Callable[[list[ProjectDict]], None],
    director_v2_service_mock: aioresponses,
    postgres_db: sa.engine.Engine,
    s4l_product_headers: dict[str, Any],
):
    # use-case 1: calling with correct product name returns 2 projects
    # projects are linked to osparc
    data, *_ = await _list_projects(client, expected)
    assert len(data) == 2
    # use-case 2: calling with another product name returns 0 projects
    # because projects are linked to osparc product in projects_to_products table
    data, *_ = await _list_projects(client, expected, headers=s4l_product_headers)
    assert len(data) == 0
    # use-case 3: remove the links to products
    # shall still return 0 because the user has no access to the services
    with postgres_db.connect() as conn:
        conn.execute(projects_to_products.delete())
    data, *_ = await _list_projects(client, expected, headers=s4l_product_headers)
    assert len(data) == 0
    data, *_ = await _list_projects(client, expected)
    assert len(data) == 0
    # use-case 4: give user access to services
    # shall return the projects for any product
    catalog_subsystem_mock([user_project, template_project])
    data, *_ = await _list_projects(client, expected, headers=s4l_product_headers)
    assert len(data) == 2
    data, *_ = await _list_projects(client, expected)
    assert len(data) == 2


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.ANONYMOUS, web.HTTPUnauthorized),
        (UserRole.GUEST, web.HTTPOk),
        (UserRole.USER, web.HTTPOk),
        (UserRole.TESTER, web.HTTPOk),
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
    expected,
    storage_subsystem_mock,
    project_db_cleaner,
    request_create_project: Callable[..., Awaitable[ProjectDict]],
):
    await request_create_project(
        client, expected.accepted, expected.created, logged_user, primary_group
    )


@pytest.mark.parametrize(*standard_role_response())
async def test_new_project_from_template(
    client: TestClient,
    logged_user: UserInfoDict,
    primary_group: dict[str, str],
    template_project,
    expected,
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
            parse_obj_as(uuidlib.UUID, node_name)


@pytest.mark.parametrize(*standard_role_response())
async def test_new_project_from_other_study(
    client: TestClient,
    logged_user: UserInfoDict,
    primary_group: dict[str, str],
    user_project: ProjectDict,
    expected,
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
            parse_obj_as(uuidlib.UUID, node_name)


@pytest.mark.parametrize(*standard_role_response())
async def test_new_project_from_template_with_body(
    client: TestClient,
    logged_user: UserInfoDict,
    primary_group: dict[str, str],
    standard_groups: list[dict[str, str]],
    template_project,
    expected,
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
            parse_obj_as(uuidlib.UUID, node_name)


@pytest.mark.parametrize(*standard_role_response())
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

        templates, *_ = await _list_projects(client, web.HTTPOk, {"type": "template"})

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
            parse_obj_as(uuidlib.UUID, node_name)

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
            parse_obj_as(uuidlib.UUID, node_name)


# PUT --------
@pytest.mark.parametrize(
    "user_role,expected,expected_change_access",
    [
        (UserRole.ANONYMOUS, web.HTTPUnauthorized, web.HTTPUnauthorized),
        (UserRole.GUEST, web.HTTPOk, web.HTTPForbidden),
        (UserRole.USER, web.HTTPOk, web.HTTPOk),
        (UserRole.TESTER, web.HTTPOk, web.HTTPOk),
    ],
)
async def test_replace_project(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    expected,
    expected_change_access,
    all_group,
    ensure_run_in_sequence_context_is_empty,
):
    project_update = deepcopy(user_project)
    project_update["description"] = "some updated from original project!!!"
    await _replace_project(client, project_update, expected)

    # replacing the owner access is not possible, it will keep the owner as well
    project_update["accessRights"].update(
        {str(all_group["gid"]): {"read": True, "write": True, "delete": True}}
    )
    await _replace_project(client, project_update, expected_change_access)


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.ANONYMOUS, web.HTTPUnauthorized),
        (UserRole.GUEST, web.HTTPOk),
        (UserRole.USER, web.HTTPOk),
        (UserRole.TESTER, web.HTTPOk),
    ],
)
async def test_replace_project_updated_inputs(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    expected,
    ensure_run_in_sequence_context_is_empty,
):
    project_update = deepcopy(user_project)
    #
    # "inputAccess": {
    #    "Na": "ReadAndWrite", <--------
    #    "Kr": "ReadOnly",
    #    "BCL": "ReadAndWrite",
    #    "NBeats": "ReadOnly",
    #    "Ligand": "Invisible",
    #    "cAMKII": "Invisible"
    #  },
    project_update["workbench"]["5739e377-17f7-4f09-a6ad-62659fb7fdec"]["inputs"][
        "Na"
    ] = 55
    await _replace_project(client, project_update, expected)


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.ANONYMOUS, web.HTTPUnauthorized),
        (UserRole.GUEST, web.HTTPOk),
        (UserRole.USER, web.HTTPOk),
        (UserRole.TESTER, web.HTTPOk),
    ],
)
async def test_replace_project_updated_readonly_inputs(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    expected,
    ensure_run_in_sequence_context_is_empty,
):
    project_update = deepcopy(user_project)
    project_update["workbench"]["5739e377-17f7-4f09-a6ad-62659fb7fdec"]["inputs"][
        "Na"
    ] = 55
    project_update["workbench"]["5739e377-17f7-4f09-a6ad-62659fb7fdec"]["inputs"][
        "Kr"
    ] = 5
    await _replace_project(client, project_update, expected)


@pytest.fixture
def random_minimal_node(faker: Faker) -> Callable[[], Node]:
    def _creator() -> Node:
        return Node(
            key=ServiceKey(f"simcore/services/comp/{faker.pystr().lower()}"),
            version=faker.numerify("#.#.#"),
            label=faker.pystr(),
        )

    return _creator


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.ANONYMOUS, web.HTTPUnauthorized),
        (UserRole.GUEST, web.HTTPConflict),
        (UserRole.USER, web.HTTPConflict),
        (UserRole.TESTER, web.HTTPConflict),
    ],
)
async def test_replace_project_adding_or_removing_nodes_raises_conflict(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    expected,
    ensure_run_in_sequence_context_is_empty,
    faker: Faker,
    random_minimal_node: Callable[[], Node],
):
    # try adding a node should not work
    project_update = deepcopy(user_project)
    new_node = random_minimal_node()
    project_update["workbench"][faker.uuid4()] = jsonable_encoder(new_node)
    await _replace_project(client, project_update, expected)
    # try removing a node should not work
    project_update = deepcopy(user_project)
    project_update["workbench"].pop(
        random.choice(list(project_update["workbench"].keys()))  # noqa: S311
    )
    await _replace_project(client, project_update, expected)


@pytest.fixture
def mock_director_v2_inactivity(
    aioresponses_mocker: aioresponses, is_inactive: bool
) -> None:
    get_services_pattern = re.compile(
        r"^http://[a-z\-_]*director-v2:[0-9]+/v2/dynamic_services/.*/inactivity.*$"
    )
    aioresponses_mocker.get(
        get_services_pattern,
        status=web.HTTPOk.status_code,
        repeat=True,
        payload={"data": {"is_inactive": is_inactive}},
    )


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.ANONYMOUS, web.HTTPUnauthorized),
        (UserRole.GUEST, web.HTTPOk),
        (UserRole.USER, web.HTTPOk),
        (UserRole.TESTER, web.HTTPOk),
    ],
)
@pytest.mark.parametrize("is_inactive", [True, False])
async def test_get_project_inactivity(
    mock_director_v2_inactivity: None,
    logged_user: UserInfoDict,
    client: TestClient,
    faker: Faker,
    user_role: UserRole,
    expected: type[web.HTTPException],
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

    assert data["data"]["is_inactive"] is is_inactive
