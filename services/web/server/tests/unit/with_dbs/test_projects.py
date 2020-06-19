# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import uuid as uuidlib
from asyncio import Future, sleep
from copy import deepcopy
from typing import Dict, List, Optional

import pytest
from aiohttp import web
from mock import call

from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_login import LoggedUser, log_client_in
from pytest_simcore.helpers.utils_projects import NewProject, delete_all_projects
from servicelib.application import create_safe_application
from simcore_service_webserver.db import setup_db
from simcore_service_webserver.db_models import UserRole
from simcore_service_webserver.director import setup_director
from simcore_service_webserver.login import setup_login
from simcore_service_webserver.projects import setup_projects
from simcore_service_webserver.projects.projects_handlers import (
    OVERRIDABLE_DOCUMENT_KEYS,
)
from simcore_service_webserver.resource_manager import setup_resource_manager
from simcore_service_webserver.rest import setup_rest
from simcore_service_webserver.security import setup_security
from simcore_service_webserver.session import setup_session
from simcore_service_webserver.socketio import setup_sockets
from simcore_service_webserver.tags import setup_tags
from simcore_service_webserver.utils import now_str, to_datetime

API_VERSION = "v0"
RESOURCE_NAME = "projects"
API_PREFIX = "/" + API_VERSION


def future_with_result(result) -> Future:
    f = Future()
    f.set_result(result)
    return f


@pytest.fixture
def mocked_director_subsystem(mocker):
    mock_director_api = {
        "get_running_interactive_services": mocker.patch(
            "simcore_service_webserver.director.director_api.get_running_interactive_services",
            return_value=future_with_result(""),
        ),
        "start_service": mocker.patch(
            "simcore_service_webserver.director.director_api.start_service",
            return_value=future_with_result(""),
        ),
        "stop_service": mocker.patch(
            "simcore_service_webserver.director.director_api.stop_service",
            return_value=future_with_result(""),
        ),
    }
    return mock_director_api


@pytest.fixture
def client(
    loop,
    aiohttp_client,
    app_cfg,
    postgres_service,
    mocked_director_subsystem,
    mock_orphaned_services,
):
    # def client(loop, aiohttp_client, app_cfg): # <<<< FOR DEVELOPMENT. DO NOT REMOVE.

    # config app
    cfg = deepcopy(app_cfg)
    port = cfg["main"]["port"]
    cfg["db"]["init_tables"] = True  # inits tables of postgres_service upon startup
    cfg["projects"]["enabled"] = True
    cfg["director"]["enabled"] = True
    cfg["resource_manager"][
        "garbage_collection_interval_seconds"
    ] = 3  # increase speed of garbage collection
    cfg["resource_manager"][
        "resource_deletion_timeout_seconds"
    ] = 3  # reduce deletion delay
    app = create_safe_application(cfg)

    # setup app
    setup_db(app)
    setup_session(app)
    setup_security(app)
    setup_rest(app)
    setup_login(app)  # needed for login_utils fixtures
    setup_resource_manager(app)
    setup_sockets(app)
    setup_director(app)
    setup_tags(app)
    assert setup_projects(app)

    # server and client
    yield loop.run_until_complete(
        aiohttp_client(app, server_kwargs={"port": port, "host": "localhost"})
    )

    # teardown here ...


@pytest.fixture()
async def logged_user(client, user_role: UserRole):
    """ adds a user in db and logs in with client

    NOTE: `user_role` fixture is defined as a parametrization below!!!
    """
    async with LoggedUser(
        client,
        {"role": user_role.name},
        check_if_succeeds=user_role != UserRole.ANONYMOUS,
    ) as user:
        print("-----> logged in user", user_role)
        yield user
        print("<----- logged out user", user_role)


@pytest.fixture()
async def logged_user2(client, user_role: UserRole):
    """ adds a user in db and logs in with client

    NOTE: `user_role` fixture is defined as a parametrization below!!!
    """
    async with LoggedUser(
        client,
        {"role": user_role.name},
        check_if_succeeds=user_role != UserRole.ANONYMOUS,
    ) as user:
        print("-----> logged in user", user_role)
        yield user
        print("<----- logged out user", user_role)


@pytest.fixture
async def user_project(client, fake_project, logged_user):
    async with NewProject(
        fake_project, client.app, user_id=logged_user["id"]
    ) as project:
        print("-----> added project", project["name"])
        yield project
        print("<----- removed project", project["name"])


@pytest.fixture
async def template_project(
    client, fake_project, logged_user, all_group: Dict[str, str]
):
    project_data = deepcopy(fake_project)
    project_data["name"] = "Fake template"
    project_data["uuid"] = "d4d0eca3-d210-4db6-84f9-63670b07176b"
    project_data["accessRights"] = {
        str(all_group["gid"]): {"read": True, "write": False, "delete": False}
    }

    async with NewProject(
        project_data, client.app, user_id=None, clear_all=True
    ) as template_project:
        print("-----> added template project", template_project["name"])
        yield template_project
        print("<----- removed template project", template_project["name"])


@pytest.fixture
def computational_system_mock(mocker):
    mock_fun = mocker.patch(
        "simcore_service_webserver.projects.projects_handlers.update_pipeline_db",
        return_value=Future(),
    )
    mock_fun.return_value.set_result("")
    return mock_fun


@pytest.fixture
def fake_services():
    def create_fakes(number_services: int) -> List[Dict]:
        fake_services = [{"service_uuid": f"{i}_uuid"} for i in range(number_services)]
        return fake_services

    yield create_fakes


@pytest.fixture
async def project_db_cleaner(client):
    yield
    await delete_all_projects(client.app)


def assert_replaced(current_project, update_data):
    def _extract(dikt, keys):
        return {k: dikt[k] for k in keys}

    modified = [
        "lastChangeDate",
    ]
    keep = [k for k in update_data.keys() if k not in modified]

    assert _extract(current_project, keep) == _extract(update_data, keep)

    k = "lastChangeDate"
    assert to_datetime(update_data[k]) < to_datetime(current_project[k])


async def _list_projects(
    client, expected: web.Response, query_parameters: Optional[Dict] = None
) -> List[Dict]:
    # GET /v0/projects
    url = client.app.router["list_projects"].url_for()
    assert str(url) == API_PREFIX + "/projects"
    if query_parameters:
        url = url.with_query(**query_parameters)

    resp = await client.get(url)
    data, errors = await assert_status(resp, expected)
    return data


# GET --------
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
    client, logged_user, user_project, template_project, expected,
):
    data = await _list_projects(client, expected)
    if data:
        assert len(data) == 2
        assert data[0] == template_project
        assert data[1] == user_project

    # GET /v0/projects?type=user
    data = await _list_projects(client, expected, {"type": "user"})
    if data:
        assert len(data) == 1
        assert data[0] == user_project

    # GET /v0/projects?type=template
    # instead /v0/projects/templates ??
    data = await _list_projects(client, expected, {"type": "template"})
    if data:
        assert len(data) == 1
        assert data[0] == template_project


async def _get_project(client, project: Dict, expected: web.Response) -> Dict:
    # GET /v0/projects/{project_id}

    # with a project owned by user
    url = client.app.router["get_project"].url_for(project_id=project["uuid"])
    assert str(url) == f"{API_PREFIX}/projects/{project['uuid']}"
    resp = await client.get(url)
    data, error = await assert_status(resp, expected)

    if not error:
        assert data == project
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
async def test_get_project(
    client, logged_user, user_project, template_project, expected,
):
    await _get_project(client, user_project, expected)

    # with a template
    await _get_project(client, template_project, expected)


async def _new_project(
    client,
    expected_response: web.Response,
    logged_user: Dict[str, str],
    primary_group: Dict[str, str],
    *,
    project: Optional[Dict] = None,
    from_template: Optional[Dict] = None,
) -> Dict:
    # POST /v0/projects
    url = client.app.router["create_projects"].url_for()
    assert str(url) == f"{API_PREFIX}/projects"
    if from_template:
        url = url.with_query(from_template=from_template["uuid"])

    # Pre-defined fields imposed by required properties in schema
    project_data = {}
    expected_data = {}
    if from_template:
        # access rights are replaced
        expected_data = deepcopy(from_template)
        expected_data["accessRights"] = {}

    if not from_template or project:
        project_data = {
            "uuid": "0000000-invalid-uuid",
            "name": "Minimal name",
            "description": "this description should not change",
            "prjOwner": "me but I will be removed anyway",
            "creationDate": now_str(),
            "lastChangeDate": now_str(),
            "thumbnail": "",
            "accessRights": {},
            "workbench": {},
            "tags": [],
        }
        if project:
            project_data.update(project)

        for key in project_data:
            expected_data[key] = project_data[key]
            if (
                key in OVERRIDABLE_DOCUMENT_KEYS
                and not project_data[key]
                and from_template
            ):
                expected_data[key] = from_template[key]

    resp = await client.post(url, json=project_data)

    new_project, error = await assert_status(resp, expected_response)
    if not error:
        # updated fields
        assert expected_data["uuid"] != new_project["uuid"]
        assert (
            new_project["prjOwner"] == logged_user["email"]
        )  # the project owner is assigned the user id e-mail
        assert to_datetime(expected_data["creationDate"]) < to_datetime(
            new_project["creationDate"]
        )
        assert to_datetime(expected_data["lastChangeDate"]) < to_datetime(
            new_project["lastChangeDate"]
        )
        # the access rights are set to use the logged user primary group + whatever was inside the project
        expected_data["accessRights"].update(
            {str(primary_group["gid"]): {"read": True, "write": True, "delete": True}}
        )
        assert new_project["accessRights"] == expected_data["accessRights"]

        # invariant fields
        modified_fields = [
            "uuid",
            "prjOwner",
            "creationDate",
            "lastChangeDate",
            "accessRights",
            "workbench" if from_template else None,
        ]

        for key in new_project.keys():
            if key not in modified_fields:
                assert expected_data[key] == new_project[key]
    return new_project


# POST --------
@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.ANONYMOUS, web.HTTPUnauthorized),
        (UserRole.GUEST, web.HTTPForbidden),
        (UserRole.USER, web.HTTPCreated),
        (UserRole.TESTER, web.HTTPCreated),
    ],
)
async def test_new_project(
    client,
    logged_user,
    primary_group,
    expected,
    computational_system_mock,
    storage_subsystem_mock,
    project_db_cleaner,
):
    new_project = await _new_project(client, expected, logged_user, primary_group)


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.ANONYMOUS, web.HTTPUnauthorized),
        (UserRole.GUEST, web.HTTPForbidden),
        (UserRole.USER, web.HTTPCreated),
        (UserRole.TESTER, web.HTTPCreated),
    ],
)
async def test_new_project_from_template(
    client,
    logged_user,
    primary_group: Dict[str, str],
    template_project,
    expected,
    computational_system_mock,
    storage_subsystem_mock,
    project_db_cleaner,
):
    new_project = await _new_project(
        client, expected, logged_user, primary_group, from_template=template_project
    )

    if new_project:
        # check uuid replacement
        for node_name in new_project["workbench"]:
            try:
                uuidlib.UUID(node_name)
            except ValueError:
                pytest.fail("Invalid uuid in workbench node {}".format(node_name))


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.ANONYMOUS, web.HTTPUnauthorized),
        (UserRole.GUEST, web.HTTPForbidden),
        (UserRole.USER, web.HTTPCreated),
        (UserRole.TESTER, web.HTTPCreated),
    ],
)
async def test_new_project_from_template_with_body(
    client,
    logged_user,
    primary_group: Dict[str, str],
    standard_groups: List[Dict[str, str]],
    template_project,
    expected,
    computational_system_mock,
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
    }
    project = await _new_project(
        client,
        expected,
        logged_user,
        primary_group,
        project=predefined,
        from_template=template_project,
    )

    if project:
        # uses predefined
        assert project["name"] == predefined["name"]
        assert project["description"] == predefined["description"]

        # different uuids for project and nodes!?
        assert project["uuid"] != template_project["uuid"]

        # check uuid replacement
        for node_name in project["workbench"]:
            try:
                uuidlib.UUID(node_name)
            except ValueError:
                pytest.fail("Invalid uuid in workbench node {}".format(node_name))


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.ANONYMOUS, web.HTTPUnauthorized),
        (UserRole.GUEST, web.HTTPForbidden),
        (UserRole.USER, web.HTTPForbidden),
        (UserRole.TESTER, web.HTTPCreated),
    ],
)
async def test_new_template_from_project(
    client,
    logged_user,
    primary_group: Dict[str, str],
    all_group: Dict[str, str],
    user_project,
    expected,
    computational_system_mock,
    storage_subsystem_mock,
    project_db_cleaner,
):
    # POST /v0/projects?as_template={user_uuid}
    url = (
        client.app.router["create_projects"]
        .url_for()
        .with_query(as_template=user_project["uuid"])
    )

    resp = await client.post(url)
    data, error = await assert_status(resp, expected)

    if not error:
        template_project = data

        templates = await _list_projects(client, web.HTTPOk, {"type": "template"})

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
            try:
                uuidlib.UUID(node_name)
            except ValueError:
                pytest.fail("Invalid uuid in workbench node {}".format(node_name))

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
    }

    resp = await client.post(url, json=predefined)
    data, error = await assert_status(resp, expected)

    if not error:
        template_project = data
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
            try:
                uuidlib.UUID(node_name)
            except ValueError:
                pytest.fail("Invalid uuid in workbench node {}".format(node_name))


@pytest.mark.parametrize(
    "user_role,expected_created,expected_ok,expected_notfound,expected_nocontents,expected_forbidden",
    [
        (
            UserRole.ANONYMOUS,
            web.HTTPUnauthorized,
            web.HTTPUnauthorized,
            web.HTTPUnauthorized,
            web.HTTPUnauthorized,
            web.HTTPUnauthorized,
        ),
        (
            UserRole.GUEST,
            web.HTTPForbidden,
            web.HTTPForbidden,
            web.HTTPNotFound,
            web.HTTPForbidden,
            web.HTTPForbidden,
        ),
        (
            UserRole.USER,
            web.HTTPCreated,
            web.HTTPOk,
            web.HTTPNotFound,
            web.HTTPNoContent,
            web.HTTPForbidden,
        ),
        (
            UserRole.TESTER,
            web.HTTPCreated,
            web.HTTPOk,
            web.HTTPNotFound,
            web.HTTPNoContent,
            web.HTTPForbidden,
        ),
    ],
)
@pytest.mark.parametrize(
    "share_rights",
    [
        {"read": True, "write": True, "delete": True},
        {"read": True, "write": True, "delete": False},
        {"read": True, "write": False, "delete": False},
        {"read": False, "write": False, "delete": False},
    ],
)
async def test_share_project(
    client,
    logged_user,
    primary_group: Dict[str, str],
    standard_groups: List[Dict[str, str]],
    all_group: Dict[str, str],
    user_role,
    expected_created,
    expected_ok,
    expected_notfound,
    expected_nocontents,
    expected_forbidden,
    storage_subsystem_mock,
    mocked_director_subsystem,
    computational_system_mock,
    share_rights,
    project_db_cleaner,
):
    # Use-case: the user shares some projects with a group

    # create a few projects
    new_project = await _new_project(
        client,
        expected_created,
        logged_user,
        primary_group,
        project={"accessRights": {str(all_group["gid"]): share_rights}},
    )
    if new_project:
        assert new_project["accessRights"] == {
            str(primary_group["gid"]): {"read": True, "write": True, "delete": True},
            str(all_group["gid"]): share_rights,
        }

        # user 1 can always get to his project
        await _get_project(client, new_project, expected_ok)

    # get another user logged in now
    user_2 = await log_client_in(
        client, {"role": user_role.name}, enable_check=user_role != UserRole.ANONYMOUS
    )
    if new_project:
        # user 2 can only get the project if user 2 has read access
        await _get_project(
            client,
            new_project,
            expected_ok if share_rights["read"] else expected_forbidden,
        )
        # user 2 can only list projects if user 2 has read access
        list_projects = await _list_projects(client, expected_ok)
        assert len(list_projects) == (1 if share_rights["read"] else 0)
        # user 2 can only update the project is user 2 has write access
        project_update = deepcopy(new_project)
        project_update["name"] = "my super name"
        await _replace_project(
            client,
            project_update,
            expected_ok if share_rights["write"] else expected_forbidden,
        )
        # user 2 can only delete projects if user 2 has delete access
        await _delete_project(
            client,
            new_project,
            expected_nocontents if share_rights["delete"] else expected_forbidden,
        )


async def _replace_project(
    client, project_update: Dict, expected: web.Response
) -> Dict:
    # PUT /v0/projects/{project_id}
    url = client.app.router["replace_project"].url_for(
        project_id=project_update["uuid"]
    )
    assert str(url) == f"{API_PREFIX}/projects/{project_update['uuid']}"
    resp = await client.put(url, json=project_update)
    data, error = await assert_status(resp, expected)
    if not error:
        assert_replaced(current_project=data, update_data=project_update)
    return data


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
    client,
    logged_user,
    user_project,
    expected,
    expected_change_access,
    computational_system_mock,
    all_group,
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
    client, logged_user, user_project, expected, computational_system_mock,
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
    client, logged_user, user_project, expected, computational_system_mock,
):
    project_update = deepcopy(user_project)
    project_update["workbench"]["5739e377-17f7-4f09-a6ad-62659fb7fdec"]["inputs"][
        "Na"
    ] = 55
    project_update["workbench"]["5739e377-17f7-4f09-a6ad-62659fb7fdec"]["inputs"][
        "Kr"
    ] = 5
    await _replace_project(client, project_update, expected)


# DELETE -------


async def _delete_project(client, project: Dict, expected: web.Response) -> None:
    url = client.app.router["delete_project"].url_for(project_id=project["uuid"])
    assert str(url) == f"{API_PREFIX}/projects/{project['uuid']}"
    resp = await client.delete(url)
    await assert_status(resp, expected)


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.ANONYMOUS, web.HTTPUnauthorized),
        (UserRole.GUEST, web.HTTPForbidden),
        (UserRole.USER, web.HTTPNoContent),
        (UserRole.TESTER, web.HTTPNoContent),
    ],
)
async def test_delete_project(
    client,
    logged_user,
    user_project,
    expected,
    storage_subsystem_mock,
    mocked_director_subsystem,
    fake_services,
):
    # DELETE /v0/projects/{project_id}

    fakes = fake_services(5)
    mocked_director_subsystem[
        "get_running_interactive_services"
    ].return_value = future_with_result(fakes)

    await _delete_project(client, user_project, expected)

    if expected == web.HTTPNoContent:
        mocked_director_subsystem[
            "get_running_interactive_services"
        ].assert_called_once()
        calls = [call(client.server.app, service["service_uuid"]) for service in fakes]
        mocked_director_subsystem["stop_service"].has_calls(calls)
        # wait for the fire&forget to run
        await sleep(2)
        await _get_project(client, user_project, web.HTTPNotFound)


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.ANONYMOUS, web.HTTPUnauthorized),
        (UserRole.GUEST, web.HTTPOk),
        (UserRole.USER, web.HTTPOk),
        (UserRole.TESTER, web.HTTPOk),
    ],
)
async def test_open_project(
    client,
    logged_user,
    user_project,
    client_session_id,
    expected,
    mocked_director_subsystem,
):
    # POST /v0/projects/{project_id}:open
    # open project

    url = client.app.router["open_project"].url_for(project_id=user_project["uuid"])
    resp = await client.post(url, json=client_session_id())
    await assert_status(resp, expected)
    if resp.status == web.HTTPOk.status_code:
        dynamic_services = {
            service_uuid: service
            for service_uuid, service in user_project["workbench"].items()
            if "/dynamic/" in service["key"]
        }
        calls = []
        for service_uuid, service in dynamic_services.items():
            calls.append(
                call(
                    client.server.app,
                    project_id=user_project["uuid"],
                    service_key=service["key"],
                    service_uuid=service_uuid,
                    service_version=service["version"],
                    user_id=logged_user["id"],
                )
            )
        mocked_director_subsystem["start_service"].assert_has_calls(calls)


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.ANONYMOUS, web.HTTPUnauthorized),
        (UserRole.GUEST, web.HTTPForbidden),
        (UserRole.USER, web.HTTPNoContent),
        (UserRole.TESTER, web.HTTPNoContent),
    ],
)
async def test_close_project(
    client,
    logged_user,
    user_project,
    client_session_id,
    expected,
    mocked_director_subsystem,
    fake_services,
):
    # POST /v0/projects/{project_id}:close
    fakes = fake_services(5)
    assert len(fakes) == 5
    mocked_director_subsystem[
        "get_running_interactive_services"
    ].return_value = future_with_result(fakes)

    # open project
    client_id = client_session_id()
    url = client.app.router["open_project"].url_for(project_id=user_project["uuid"])
    resp = await client.post(url, json=client_id)

    if resp.status == web.HTTPOk.status_code:
        calls = [
            call(client.server.app, user_project["uuid"], logged_user["id"]),
        ]
        mocked_director_subsystem["get_running_interactive_services"].has_calls(calls)
        mocked_director_subsystem["get_running_interactive_services"].reset_mock()

    # close project
    url = client.app.router["close_project"].url_for(project_id=user_project["uuid"])
    resp = await client.post(url, json=client_id)
    await assert_status(resp, expected)
    if resp.status == web.HTTPNoContent.status_code:
        calls = [
            call(client.server.app, user_project["uuid"], None),
            call(client.server.app, user_project["uuid"], logged_user["id"]),
        ]
        mocked_director_subsystem["get_running_interactive_services"].has_calls(calls)
        calls = [call(client.server.app, service["service_uuid"]) for service in fakes]
        mocked_director_subsystem["stop_service"].has_calls(calls)


@pytest.mark.parametrize(
    "user_role, expected",
    [
        # (UserRole.ANONYMOUS, web.HTTPUnauthorized),
        (UserRole.GUEST, web.HTTPOk),
        (UserRole.USER, web.HTTPOk),
        (UserRole.TESTER, web.HTTPOk),
    ],
)
async def test_get_active_project(
    client,
    logged_user,
    user_project,
    client_session_id,
    expected,
    socketio_client,
    mocked_director_subsystem,
):
    # login with socket using client session id
    client_id1 = client_session_id()
    sio = await socketio_client(client_id1)
    assert sio.sid
    # get active projects -> empty
    get_active_projects_url = (
        client.app.router["get_active_project"]
        .url_for()
        .with_query(client_session_id=client_id1)
    )
    resp = await client.get(get_active_projects_url)
    data, error = await assert_status(resp, expected)
    if resp.status == web.HTTPOk.status_code:
        assert not data
        assert not error

    # open project
    open_project_url = client.app.router["open_project"].url_for(
        project_id=user_project["uuid"]
    )
    resp = await client.post(open_project_url, json=client_id1)
    data, error = await assert_status(resp, expected)
    resp = await client.get(get_active_projects_url)
    data, error = await assert_status(resp, expected)
    if resp.status == web.HTTPOk.status_code:
        assert not error
        assert data == user_project

    # login with socket using client session id2
    client_id2 = client_session_id()
    sio = await socketio_client(client_id2)
    assert sio.sid
    # get active projects -> empty
    get_active_projects_url = (
        client.app.router["get_active_project"]
        .url_for()
        .with_query(client_session_id=client_id2)
    )
    resp = await client.get(get_active_projects_url)
    data, error = await assert_status(resp, expected)
    if resp.status == web.HTTPOk.status_code:
        assert not data
        assert not error


@pytest.mark.parametrize(
    "user_role, expected",
    [
        # (UserRole.ANONYMOUS),
        (UserRole.GUEST, web.HTTPForbidden),
        (UserRole.USER, web.HTTPForbidden),
        (UserRole.TESTER, web.HTTPForbidden),
    ],
)
async def test_delete_shared_project_forbidden(
    client,
    logged_user,
    user_project,
    mocked_director_api,
    mocked_dynamic_service,
    socketio_client,
    client_session_id,
    expected,
    mocked_director_subsystem,
):
    # service in project = await mocked_dynamic_service(logged_user["id"], empty_user_project["uuid"])
    service = await mocked_dynamic_service(logged_user["id"], user_project["uuid"])
    # open project in tab1
    client_session_id1 = client_session_id()
    sio1 = await socketio_client(client_session_id1)
    url = client.app.router["open_project"].url_for(project_id=user_project["uuid"])
    resp = await client.post(url, json=client_session_id1)
    await assert_status(resp, web.HTTPOk)
    # delete project in tab2
    client_session_id2 = client_session_id()
    sio2 = await socketio_client(client_session_id2)
    await _delete_project(client, user_project, expected)


@pytest.mark.parametrize(
    "user_role, create_exp, get_exp, deletion_exp",
    [
        (
            UserRole.ANONYMOUS,
            web.HTTPUnauthorized,
            web.HTTPUnauthorized,
            web.HTTPUnauthorized,
        ),
        (UserRole.GUEST, web.HTTPForbidden, web.HTTPOk, web.HTTPForbidden),
        (UserRole.USER, web.HTTPCreated, web.HTTPOk, web.HTTPNoContent),
        (UserRole.TESTER, web.HTTPCreated, web.HTTPOk, web.HTTPNoContent),
    ],
)
async def test_project_node_lifetime(
    client,
    logged_user,
    user_project,
    create_exp,
    get_exp,
    deletion_exp,
    mocked_director_subsystem,
    storage_subsystem_mock,
    mocker,
):

    mock_storage_api_delete_data_folders_of_project_node = mocker.patch(
        "simcore_service_webserver.projects.projects_handlers.projects_api.delete_data_folders_of_project_node",
        return_value=Future(),
    )
    mock_storage_api_delete_data_folders_of_project_node.return_value.set_result("")

    # create a new dynamic node...
    url = client.app.router["create_node"].url_for(project_id=user_project["uuid"])
    body = {"service_key": "some/dynamic/key", "service_version": "1.3.4"}
    resp = await client.post(url, json=body)
    data, errors = await assert_status(resp, create_exp)
    node_id = "wrong_node_id"
    if resp.status == web.HTTPCreated.status_code:
        mocked_director_subsystem["start_service"].assert_called_once()
        assert "node_id" in data
        node_id = data["node_id"]
    else:
        mocked_director_subsystem["start_service"].assert_not_called()
    # create a new NOT dynamic node...
    mocked_director_subsystem["start_service"].reset_mock()
    url = client.app.router["create_node"].url_for(project_id=user_project["uuid"])
    body = {"service_key": "some/notdynamic/key", "service_version": "1.3.4"}
    resp = await client.post(url, json=body)
    data, errors = await assert_status(resp, create_exp)
    node_id_2 = "wrong_node_id"
    if resp.status == web.HTTPCreated.status_code:
        mocked_director_subsystem["start_service"].assert_not_called()
        assert "node_id" in data
        node_id_2 = data["node_id"]
    else:
        mocked_director_subsystem["start_service"].assert_not_called()

    # get the node state
    mocked_director_subsystem[
        "get_running_interactive_services"
    ].return_value = future_with_result(
        [{"service_uuid": node_id, "service_state": "running"}]
    )
    url = client.app.router["get_node"].url_for(
        project_id=user_project["uuid"], node_id=node_id
    )
    resp = await client.get(url)
    data, errors = await assert_status(resp, get_exp)
    if resp.status == web.HTTPOk.status_code:
        assert "service_state" in data
        assert data["service_state"] == "running"

    # get the NOT dynamic node state
    mocked_director_subsystem[
        "get_running_interactive_services"
    ].return_value = future_with_result("")

    url = client.app.router["get_node"].url_for(
        project_id=user_project["uuid"], node_id=node_id_2
    )
    resp = await client.get(url)
    data, errors = await assert_status(resp, get_exp)
    if resp.status == web.HTTPOk.status_code:
        assert "service_state" in data
        assert data["service_state"] == "idle"

    # delete the node
    mocked_director_subsystem[
        "get_running_interactive_services"
    ].return_value = future_with_result([{"service_uuid": node_id}])
    url = client.app.router["delete_node"].url_for(
        project_id=user_project["uuid"], node_id=node_id
    )
    resp = await client.delete(url)
    data, errors = await assert_status(resp, deletion_exp)
    if resp.status == web.HTTPNoContent.status_code:
        mocked_director_subsystem["stop_service"].assert_called_once()
        mock_storage_api_delete_data_folders_of_project_node.assert_called_once()
    else:
        mocked_director_subsystem["stop_service"].assert_not_called()
        mock_storage_api_delete_data_folders_of_project_node.assert_not_called()

    # delete the NOT dynamic node
    mocked_director_subsystem["stop_service"].reset_mock()
    mock_storage_api_delete_data_folders_of_project_node.reset_mock()
    # mock_director_api_get_running_services.return_value.set_result([{"service_uuid": node_id}])
    url = client.app.router["delete_node"].url_for(
        project_id=user_project["uuid"], node_id=node_id_2
    )
    resp = await client.delete(url)
    data, errors = await assert_status(resp, deletion_exp)
    if resp.status == web.HTTPNoContent.status_code:
        mocked_director_subsystem["stop_service"].assert_not_called()
        mock_storage_api_delete_data_folders_of_project_node.assert_called_once()
    else:
        mocked_director_subsystem["stop_service"].assert_not_called()
        mock_storage_api_delete_data_folders_of_project_node.assert_not_called()


@pytest.mark.parametrize("user_role,expected", [(UserRole.USER, web.HTTPOk)])
async def test_tags_to_studies(
    client, logged_user, user_project, expected, test_tags_data,
):
    # Add test tags
    tags = test_tags_data
    added_tags = []
    for tag in tags:
        url = client.app.router["create_tag"].url_for()
        resp = await client.post(url, json=tag)
        added_tag, _ = await assert_status(resp, expected)
        added_tags.append(added_tag)
        # Add tag to study
        url = client.app.router["add_tag"].url_for(
            study_uuid=user_project.get("uuid"), tag_id=str(added_tag.get("id"))
        )
        resp = await client.put(url)
        data, _ = await assert_status(resp, expected)
        # Tag is included in response
        assert added_tag.get("id") in data.get("tags")

    # check the tags are in
    user_project["tags"] = [tag["id"] for tag in added_tags]
    data = await _get_project(client, user_project, expected)

    # Delete tag0
    url = client.app.router["delete_tag"].url_for(tag_id=str(added_tags[0].get("id")))
    resp = await client.delete(url)
    await assert_status(resp, web.HTTPNoContent)
    # Get project and check that tag is no longer there
    user_project["tags"].remove(added_tags[0]["id"])
    data = await _get_project(client, user_project, expected)
    assert added_tags[0].get("id") not in data.get("tags")

    # Remove tag1 from project
    url = client.app.router["remove_tag"].url_for(
        study_uuid=user_project.get("uuid"), tag_id=str(added_tags[1].get("id"))
    )
    resp = await client.delete(url)
    await assert_status(resp, expected)
    # Get project and check that tag is no longer there
    user_project["tags"].remove(added_tags[1]["id"])
    data = await _get_project(client, user_project, expected)
    assert added_tags[1].get("id") not in data.get("tags")

    # Delete tag1
    url = client.app.router["delete_tag"].url_for(tag_id=str(added_tags[1].get("id")))
    resp = await client.delete(url)
    await assert_status(resp, web.HTTPNoContent)
