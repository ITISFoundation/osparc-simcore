# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import asyncio
import uuid as uuidlib
from copy import deepcopy
from math import ceil
from typing import Any, Callable, Dict, List, Optional, Tuple, Type, Union
from unittest.mock import call

import aiohttp
import pytest
from _helpers import ExpectedResponse, standard_role_response
from aiohttp import web
from aiohttp.test_utils import TestClient
from aioresponses import aioresponses
from models_library.projects_access import Owner
from models_library.projects_state import (
    ProjectLocked,
    ProjectRunningState,
    ProjectState,
    ProjectStatus,
    RunningState,
)
from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_projects import NewProject, delete_all_projects
from servicelib import async_utils
from servicelib.application import create_safe_application
from simcore_service_webserver import catalog
from simcore_service_webserver.db import setup_db
from simcore_service_webserver.db_models import UserRole
from simcore_service_webserver.director import setup_director
from simcore_service_webserver.director_v2 import setup_director_v2
from simcore_service_webserver.login import setup_login
from simcore_service_webserver.products import setup_products
from simcore_service_webserver.projects import setup_projects
from simcore_service_webserver.projects.projects_handlers import (
    OVERRIDABLE_DOCUMENT_KEYS,
)
from simcore_service_webserver.resource_manager import setup_resource_manager
from simcore_service_webserver.rest import setup_rest
from simcore_service_webserver.security import setup_security
from simcore_service_webserver.session import setup_session
from simcore_service_webserver.socketio import setup_socketio
from simcore_service_webserver.tags import setup_tags
from simcore_service_webserver.utils import now_str, to_datetime
from socketio.exceptions import ConnectionError as SocketConnectionError
from yarl import URL

API_VERSION = "v0"
RESOURCE_NAME = "projects"
API_PREFIX = "/" + API_VERSION


DEFAULT_GARBAGE_COLLECTOR_INTERVAL_SECONDS: int = 3
DEFAULT_GARBAGE_COLLECTOR_DELETION_TIMEOUT_SECONDS: int = 3


@pytest.fixture
def client(
    loop,
    aiohttp_client,
    app_cfg,
    postgres_db,
    mocked_director_v2_api,
    mock_orphaned_services,
    redis_client,
):

    # config app
    cfg = deepcopy(app_cfg)
    port = cfg["main"]["port"]
    cfg["projects"]["enabled"] = True
    cfg["director"]["enabled"] = True
    cfg["resource_manager"][
        "garbage_collection_interval_seconds"
    ] = DEFAULT_GARBAGE_COLLECTOR_INTERVAL_SECONDS  # increase speed of garbage collection
    cfg["resource_manager"][
        "resource_deletion_timeout_seconds"
    ] = DEFAULT_GARBAGE_COLLECTOR_DELETION_TIMEOUT_SECONDS  # reduce deletion delay
    app = create_safe_application(cfg)

    # setup app
    setup_db(app)
    setup_session(app)
    setup_security(app)
    setup_rest(app)
    setup_login(app)  # needed for login_utils fixtures
    setup_resource_manager(app)
    setup_socketio(app)
    setup_director(app)
    setup_director_v2(app)
    setup_tags(app)
    assert setup_projects(app)
    setup_products(app)

    # server and client
    yield loop.run_until_complete(
        aiohttp_client(app, server_kwargs={"port": port, "host": "localhost"})
    )

    # teardown here ...


@pytest.fixture()
def ensure_run_in_sequence_context_is_empty():
    async_utils.sequential_jobs_contexts = {}


@pytest.fixture
def mocks_on_projects_api(mocker, logged_user) -> None:
    """
    All projects in this module are UNLOCKED

    Emulates that it found logged_user as the SOLE user of this project
    and returns the  ProjectState indicating his as owner
    """
    nameparts = logged_user["name"].split(".") + [""]
    state = ProjectState(
        locked=ProjectLocked(
            value=False,
            owner=Owner(
                user_id=logged_user["id"],
                first_name=nameparts[0],
                last_name=nameparts[1],
            ),
            status=ProjectStatus.CLOSED,
        ),
        state=ProjectRunningState(value=RunningState.NOT_STARTED),
    )
    mocker.patch(
        "simcore_service_webserver.projects.projects_api._get_project_lock_state",
        return_value=state,
    )


@pytest.fixture
async def user_project(client, fake_project, logged_user):
    async with NewProject(
        fake_project, client.app, user_id=logged_user["id"]
    ) as project:
        print("-----> added project", project["name"])
        yield project
        print("<----- removed project", project["name"])


@pytest.fixture
async def shared_project(client, fake_project, logged_user, all_group):
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
def fake_services():
    def create_fakes(number_services: int) -> List[Dict]:
        fake_services = [{"service_uuid": f"{i}_uuid"} for i in range(number_services)]
        return fake_services

    yield create_fakes


@pytest.fixture
async def project_db_cleaner(client):
    yield
    await delete_all_projects(client.app)


@pytest.fixture
async def catalog_subsystem_mock(
    monkeypatch,
) -> Callable[[Optional[Union[List[Dict], Dict]]], None]:
    services_in_project = []

    def creator(projects: Optional[Union[List[Dict], Dict]] = None) -> None:
        for proj in projects:
            services_in_project.extend(
                [
                    {"key": s["key"], "version": s["version"]}
                    for _, s in proj["workbench"].items()
                ]
            )

    async def mocked_get_services_for_user(*args, **kwargs):
        return services_in_project

    monkeypatch.setattr(
        catalog, "get_services_for_user_in_product", mocked_get_services_for_user
    )

    return creator


@pytest.fixture(autouse=True)
async def director_v2_automock(
    director_v2_service_mock: aioresponses,
) -> aioresponses:
    yield director_v2_service_mock


# HELPERS -----------------------------------------------------------------------------------------


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
    client,
    expected: Type[web.HTTPException],
    query_parameters: Optional[Dict] = None,
    expected_error_msg: Optional[str] = None,
    expected_error_code: Optional[str] = None,
) -> Tuple[List[Dict], Dict[str, Any], Dict[str, Any]]:
    if not query_parameters:
        query_parameters = {}
    # GET /v0/projects
    url = client.app.router["list_projects"].url_for()
    assert str(url) == API_PREFIX + "/projects"
    if query_parameters:
        url = url.with_query(**query_parameters)

    resp = await client.get(url)
    data, errors, meta, links = await assert_status(
        resp,
        expected,
        expected_msg=expected_error_msg,
        expected_error_code=expected_error_code,
        include_meta=True,
        include_links=True,
    )
    if data:
        assert meta is not None
        # see [api/specs/webserver/openapi-projects.yaml] for defaults
        exp_offset = max(int(query_parameters.get("offset", 0)), 0)
        exp_limit = max(1, min(int(query_parameters.get("limit", 20)), 50))
        assert meta["offset"] == exp_offset
        assert meta["limit"] == exp_limit
        exp_last_page = ceil(meta["total"] / meta["limit"] - 1)
        assert links is not None
        complete_url = client.make_url(url)
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
            assert links["prev"] == None
        else:
            assert links["prev"] == str(
                URL(complete_url).update_query(
                    {"offset": max(exp_offset - exp_limit, 0), "limit": exp_limit}
                )
            )
        if exp_offset >= (exp_last_page * exp_limit):
            assert links["next"] == None
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
    client,
    project: Dict,
    expected: Type[web.HTTPException],
) -> Dict:
    # GET /v0/projects/{project_id}

    # with a project owned by user
    url = client.app.router["get_project"].url_for(project_id=project["uuid"])
    assert str(url) == f"{API_PREFIX}/projects/{project['uuid']}"
    resp = await client.get(url)
    data, error = await assert_status(resp, expected)

    if not error:
        project_state = data.pop("state")
        assert data == project
        assert ProjectState(**project_state)
    return data


async def _new_project(
    client,
    expected_response: Type[web.HTTPException],
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
            "classifiers": [],
            "ui": {},
            "dev": {},
            "quality": {},
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
        # has project state
        assert not ProjectState(
            **new_project.pop("state")
        ).locked.value, "Newly created projects should be unlocked"

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
            "ui" if from_template else None,
        ]

        for key in new_project.keys():
            if key not in modified_fields:
                assert expected_data[key] == new_project[key]
    return new_project


async def _replace_project(
    client, project_update: Dict, expected: Type[web.HTTPException]
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


async def _delete_project(
    client, project: Dict, expected: Type[web.HTTPException]
) -> None:
    url = client.app.router["delete_project"].url_for(project_id=project["uuid"])
    assert str(url) == f"{API_PREFIX}/projects/{project['uuid']}"
    resp = await client.delete(url)
    await assert_status(resp, expected)


# TESTS ----------------------------------------------------------------------------------------------------
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
    logged_user: Dict[str, Any],
    user_project: Dict[str, Any],
    template_project: Dict[str, Any],
    expected: Type[web.HTTPException],
    catalog_subsystem_mock: Callable[[Optional[Union[List[Dict], Dict]]], None],
    director_v2_service_mock: aioresponses,
):
    catalog_subsystem_mock([user_project, template_project])
    data, *_ = await _list_projects(client, expected)

    if data:
        assert len(data) == 2

        project_state = data[0].pop("state")
        assert data[0] == template_project
        assert not ProjectState(
            **project_state
        ).locked.value, "Templates are not locked"

        project_state = data[1].pop("state")
        assert data[1] == user_project
        assert ProjectState(**project_state)

    # GET /v0/projects?type=user
    data, *_ = await _list_projects(client, expected, {"type": "user"})
    if data:
        assert len(data) == 1
        project_state = data[0].pop("state")
        assert data[0] == user_project
        assert not ProjectState(
            **project_state
        ).locked.value, "Single user does not lock"

    # GET /v0/projects?type=template
    # instead /v0/projects/templates ??
    data, *_ = await _list_projects(client, expected, {"type": "template"})
    if data:
        assert len(data) == 1
        project_state = data[0].pop("state")
        assert data[0] == template_project
        assert not ProjectState(
            **project_state
        ).locked.value, "Templates are not locked"


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
    client,
    logged_user,
    user_project,
    template_project,
    expected,
    catalog_subsystem_mock,
):
    catalog_subsystem_mock([user_project, template_project])

    # standard project
    await _assert_get_same_project(client, user_project, expected)

    # with a template
    await _assert_get_same_project(client, template_project, expected)


# POST --------
@pytest.mark.parametrize(*standard_role_response())
async def test_new_project(
    client,
    logged_user,
    primary_group,
    expected,
    storage_subsystem_mock,
    project_db_cleaner,
):
    new_project = await _new_project(
        client, expected.created, logged_user, primary_group
    )


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
    new_project = await _new_project(
        client,
        expected.created,
        logged_user,
        primary_group,
        from_template=template_project,
    )

    if new_project:
        # check uuid replacement
        for node_name in new_project["workbench"]:
            try:
                uuidlib.UUID(node_name)
            except ValueError:
                pytest.fail("Invalid uuid in workbench node {}".format(node_name))


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
    project = await _new_project(
        client,
        expected.created,
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
        (UserRole.USER, web.HTTPCreated),
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
    storage_subsystem_mock,
    catalog_subsystem_mock,
    project_db_cleaner,
    mocks_on_projects_api,
):
    # POST /v0/projects?as_template={project_uuid}
    url = (
        client.app.router["create_projects"]
        .url_for()
        .with_query(as_template=user_project["uuid"])
    )

    resp = await client.post(url)
    data, error = await assert_status(resp, expected)

    if not error:
        template_project = data
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
        "classifiers": [],
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
    client, logged_user, user_project, expected, ensure_run_in_sequence_context_is_empty
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
    client, logged_user, user_project, expected, ensure_run_in_sequence_context_is_empty
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
    mocked_director_v2_api,
    catalog_subsystem_mock,
    fake_services,
):
    # DELETE /v0/projects/{project_id}

    fakes = fake_services(5)
    mocked_director_v2_api["director_v2.get_services"].return_value = fakes

    await _delete_project(client, user_project, expected)
    await asyncio.sleep(2)  # let some time fly for the background tasks to run

    if expected == web.HTTPNoContent:
        mocked_director_v2_api["director_v2.get_services"].assert_called_once()

        expected_calls = [
            call(
                app=client.server.app,
                service_uuid=service["service_uuid"],
                save_state=True,
            )
            for service in fakes
        ]
        mocked_director_v2_api["director_v2.stop_service"].assert_has_calls(
            expected_calls
        )

        # wait for the fire&forget to run
        await asyncio.sleep(2)
        await _assert_get_same_project(client, user_project, web.HTTPNotFound)


@pytest.mark.parametrize(
    "user_role, expected_ok, expected_forbidden",
    [
        (UserRole.ANONYMOUS, web.HTTPUnauthorized, web.HTTPUnauthorized),
        (UserRole.GUEST, web.HTTPOk, web.HTTPForbidden),
        (UserRole.USER, web.HTTPOk, web.HTTPForbidden),
        (UserRole.TESTER, web.HTTPOk, web.HTTPForbidden),
    ],
)
async def test_delete_multiple_opened_project_forbidden(
    client,
    logged_user,
    user_project,
    mocked_director_v2_api,
    mocked_dynamic_service,
    socketio_client_factory: Callable,
    client_session_id_factory: Callable,
    user_role,
    expected_ok,
    expected_forbidden,
):
    # service in project = await mocked_dynamic_service(logged_user["id"], empty_user_project["uuid"])
    service = await mocked_dynamic_service(logged_user["id"], user_project["uuid"])
    # open project in tab1
    client_session_id1 = client_session_id_factory()
    try:
        sio1 = await socketio_client_factory(client_session_id1)
    except SocketConnectionError:
        if user_role != UserRole.ANONYMOUS:
            pytest.fail("socket io connection should not fail")
    url = client.app.router["open_project"].url_for(project_id=user_project["uuid"])
    resp = await client.post(url, json=client_session_id1)
    await assert_status(resp, expected_ok)
    # delete project in tab2
    client_session_id2 = client_session_id_factory()
    try:
        sio2 = await socketio_client_factory(client_session_id2)
    except SocketConnectionError:
        if user_role != UserRole.ANONYMOUS:
            pytest.fail("socket io connection should not fail")
    await _delete_project(client, user_project, expected_forbidden)


# PAGINATION
def standard_user_role() -> Tuple[str, Tuple[UserRole, ExpectedResponse]]:
    all_roles = standard_role_response()

    return (all_roles[0], [pytest.param(*all_roles[1][2], id="standard user role")])


@pytest.mark.parametrize(
    "limit, offset, expected_error_msg",
    [
        (-7, 0, "Invalid parameter value for `limit`"),
        (0, 0, "Invalid parameter value for `limit`"),
        (43, -2, "Invalid parameter value for `offset`"),
    ],
)
@pytest.mark.parametrize(*standard_user_role())
async def test_list_projects_with_invalid_pagination_parameters(
    client: TestClient,
    logged_user: Dict[str, Any],
    primary_group: Dict[str, str],
    expected: ExpectedResponse,
    storage_subsystem_mock,
    catalog_subsystem_mock: Callable[[Optional[Union[List[Dict], Dict]]], None],
    director_v2_service_mock: aioresponses,
    project_db_cleaner,
    limit: int,
    offset: int,
    expected_error_msg: str,
):
    await _list_projects(
        client,
        web.HTTPBadRequest,
        query_parameters={"limit": limit, "offset": offset},
        expected_error_msg=expected_error_msg,
        expected_error_code="InvalidParameterValue",
    )


@pytest.mark.parametrize("limit", [7, 20, 43])
@pytest.mark.parametrize(*standard_user_role())
async def test_list_projects_with_pagination(
    client: TestClient,
    logged_user: Dict[str, Any],
    primary_group: Dict[str, str],
    expected: ExpectedResponse,
    storage_subsystem_mock,
    catalog_subsystem_mock: Callable[[Optional[Union[List[Dict], Dict]]], None],
    director_v2_service_mock: aioresponses,
    project_db_cleaner,
    limit: int,
):

    NUM_PROJECTS = 90
    # let's create a few projects here
    created_projects = await asyncio.gather(
        *[
            _new_project(client, expected.created, logged_user, primary_group)
            for i in range(NUM_PROJECTS)
        ]
    )
    if expected.created == web.HTTPCreated:
        catalog_subsystem_mock(created_projects)

        assert len(created_projects) == NUM_PROJECTS
        NUMBER_OF_CALLS = ceil(NUM_PROJECTS / limit)
        next_link = None
        default_query_parameter = {"limit": limit}
        projects = []
        for i in range(NUMBER_OF_CALLS):
            print(
                "calling in with query",
                next_link.query if next_link else default_query_parameter,
            )
            data, meta, links = await _list_projects(
                client,
                expected.ok,
                query_parameters=next_link.query
                if next_link
                else default_query_parameter,
            )
            print("...received [", meta, "]")
            assert len(data) == meta["count"]
            assert meta["count"] == min(limit, NUM_PROJECTS - len(projects))
            assert meta["limit"] == limit
            projects.extend(data)
            next_link = URL(links["next"]) if links["next"] is not None else None

        assert len(projects) == len(created_projects)
        assert {prj["uuid"] for prj in projects} == {
            prj["uuid"] for prj in created_projects
        }
