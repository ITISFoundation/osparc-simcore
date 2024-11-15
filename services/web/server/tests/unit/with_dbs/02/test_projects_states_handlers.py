# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=too-many-positional-arguments
# pylint: disable=too-many-statements
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import asyncio
import time
from collections.abc import Awaitable, Callable, Iterator
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from typing import Any
from unittest import mock
from unittest.mock import call

import pytest
import socketio
import sqlalchemy as sa
from aiohttp import ClientResponse
from aiohttp.test_utils import TestClient, TestServer
from faker import Faker
from models_library.api_schemas_directorv2.dynamic_services import DynamicServiceGet
from models_library.api_schemas_dynamic_scheduler.dynamic_services import (
    DynamicServiceStart,
    DynamicServiceStop,
)
from models_library.api_schemas_webserver.projects_nodes import NodeGet, NodeGetIdle
from models_library.projects import ProjectID
from models_library.projects_access import Owner
from models_library.projects_state import (
    ProjectLocked,
    ProjectRunningState,
    ProjectState,
    ProjectStatus,
    RunningState,
)
from models_library.services_enums import ServiceState
from models_library.services_resources import (
    ServiceResourcesDict,
    ServiceResourcesDictHelpers,
)
from models_library.utils.fastapi_encoders import jsonable_encoder
from pydantic import PositiveInt
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.webserver_login import UserInfoDict, log_client_in
from pytest_simcore.helpers.webserver_parametrizations import (
    ExpectedResponse,
    standard_role_response,
)
from pytest_simcore.helpers.webserver_projects import assert_get_same_project
from servicelib.aiohttp import status
from servicelib.common_headers import UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE
from simcore_postgres_database.models.products import products
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver.db.models import UserRole
from simcore_service_webserver.projects.models import ProjectDict
from simcore_service_webserver.socketio.messages import SOCKET_IO_PROJECT_UPDATED_EVENT
from simcore_service_webserver.utils import to_datetime
from socketio.exceptions import ConnectionError as SocketConnectionError

RESOURCE_NAME = "projects"
API_PREFIX = f"/{API_VTAG}"


@pytest.fixture
def app_environment(
    app_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch
) -> EnvVarsDict:
    # disable the garbage collector
    monkeypatch.setenv("WEBSERVER_GARBAGE_COLLECTOR", "null")
    return app_environment | {"WEBSERVER_GARBAGE_COLLECTOR": "null"}


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
    expected: HTTPStatus,
    query_parameters: dict | None = None,
) -> list[ProjectDict]:

    assert client.app

    # GET /v0/projects
    url = client.app.router["list_projects"].url_for()
    assert str(url) == API_PREFIX + "/projects"
    if query_parameters:
        url = url.with_query(**query_parameters)

    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, expected)
    return data


async def _replace_project(
    client: TestClient, project_update: ProjectDict, expected: HTTPStatus
) -> ProjectDict:
    assert client.app

    # PATCH /v0/projects/{project_id}
    url = client.app.router["patch_project"].url_for(project_id=project_update["uuid"])
    assert str(url) == f"{API_PREFIX}/projects/{project_update['uuid']}"
    resp = await client.patch(f"{url}", json=project_update)
    data, error = await assert_status(resp, expected)
    if not error:
        url = client.app.router["get_project"].url_for(
            project_id=project_update["uuid"]
        )
        resp = await client.get(f"{url}")
        get_data, _ = await assert_status(resp, HTTPStatus.OK)
        assert_replaced(current_project=get_data, update_data=project_update)
    return data


async def _connect_websocket(
    socketio_client_factory: Callable,
    check_connection: bool,
    client: TestClient,
    client_id: str,
    events: dict[str, Callable] | None = None,
) -> socketio.AsyncClient | None:
    try:
        sio = await socketio_client_factory(client_id, client)
        assert sio.sid
        if events:
            for event, handler in events.items():
                sio.on(event, handler=handler)
        return sio
    except SocketConnectionError:
        if check_connection:
            pytest.fail("socket io connection should not fail")


async def _open_project(
    client: TestClient,
    client_id: str,
    project: ProjectDict,
    expected: HTTPStatus | list[HTTPStatus],
) -> tuple[dict, dict]:
    assert client.app

    url = client.app.router["open_project"].url_for(project_id=project["uuid"])
    resp = await client.post(f"{url}", json=client_id)

    if isinstance(expected, list):
        for e in expected:
            try:
                data, error = await assert_status(resp, e)
                return data, error
            except AssertionError:  # noqa: PERF203
                # re-raise if last item
                if e == expected[-1]:
                    raise
                continue
    else:
        data, error = await assert_status(resp, expected)
        return data, error

    msg = "could not open project"
    raise AssertionError(msg)


async def _close_project(
    client: TestClient, client_id: str, project: dict, expected: HTTPStatus
):
    assert client.app

    url = client.app.router["close_project"].url_for(project_id=project["uuid"])
    resp = await client.post(f"{url}", json=client_id)
    await assert_status(resp, expected)


async def _state_project(
    client: TestClient,
    project: dict,
    expected: HTTPStatus,
    expected_project_state: ProjectState,
):
    assert client.app

    url = client.app.router["get_project_state"].url_for(project_id=project["uuid"])
    resp = await client.get(f"{url}")
    data, error = await assert_status(resp, expected)
    if not error:
        # the project is locked
        received_state = ProjectState(**data)
        assert received_state == expected_project_state


async def _assert_project_state_updated(
    handler: mock.Mock,
    shared_project: dict,
    expected_project_state_updates: list[ProjectState],
) -> None:
    if not expected_project_state_updates:
        handler.assert_not_called()
    else:
        # wait for the calls
        now = time.monotonic()
        MAX_WAITING_TIME = 15
        while time.monotonic() - now < MAX_WAITING_TIME:
            await asyncio.sleep(1)
            if handler.call_count == len(expected_project_state_updates):
                break
        if time.monotonic() - now > MAX_WAITING_TIME:
            pytest.fail(
                f"waited more than {MAX_WAITING_TIME}s and got only {handler.call_count}/{len(expected_project_state_updates)} calls"
            )

        calls = [
            call(
                jsonable_encoder(
                    {
                        "project_uuid": shared_project["uuid"],
                        "data": p_state.model_dump(by_alias=True, exclude_unset=True),
                    }
                )
            )
            for p_state in expected_project_state_updates
        ]
        handler.assert_has_calls(calls)
        handler.reset_mock()


async def _delete_project(client: TestClient, project: dict) -> ClientResponse:
    assert client.app

    url = client.app.router["delete_project"].url_for(project_id=project["uuid"])
    assert str(url) == f"{API_PREFIX}/projects/{project['uuid']}"
    return await client.delete(f"{url}")


@pytest.mark.parametrize(*standard_role_response())
@pytest.mark.parametrize(
    "share_rights",
    [
        {"read": True, "write": True, "delete": True},
        {"read": True, "write": True, "delete": False},
        {"read": True, "write": False, "delete": False},
        {"read": False, "write": False, "delete": False},
    ],
    ids=str,
)
async def test_share_project(
    client: TestClient,
    logged_user: dict,
    primary_group: dict[str, str],
    standard_groups: list[dict[str, str]],
    all_group: dict[str, str],
    user_role: UserRole,
    expected: ExpectedResponse,
    storage_subsystem_mock,
    mocked_director_v2_api: dict[str, mock.Mock],
    catalog_subsystem_mock: Callable[[list[ProjectDict]], None],
    share_rights: dict,
    project_db_cleaner,
    request_create_project: Callable[..., Awaitable[ProjectDict]],
):
    # Use-case: the user shares some projects with a group

    # create a few projects
    new_project = await request_create_project(
        client,
        expected.accepted,
        expected.created,
        logged_user,
        primary_group,
        project={"accessRights": {str(all_group["gid"]): share_rights}},
    )
    if new_project:
        assert new_project["accessRights"] == {
            f'{primary_group["gid"]}': {"read": True, "write": True, "delete": True},
            f'{(all_group["gid"])}': share_rights,
        }

        # user 1 can always get to his project
        await assert_get_same_project(client, new_project, expected.ok)

    # get another user logged in now
    await log_client_in(
        client, {"role": user_role.name}, enable_check=user_role != UserRole.ANONYMOUS
    )
    if new_project:
        # user 2 can get the project if user 2 has read access
        await assert_get_same_project(
            client,
            new_project,
            expected.ok if share_rights["read"] else expected.forbidden,
        )

        # user 2 can list projects if user 2 has read access
        list_projects = await _list_projects(client, expected.ok)
        assert len(list_projects) == (1 if share_rights["read"] else 0)

        # user 2 can update the project if user 2 has write access
        project_update = deepcopy(new_project)
        project_update["name"] = "my super name"
        project_update.pop("accessRights")
        await _replace_project(
            client,
            project_update,
            expected.no_content if share_rights["write"] else expected.forbidden,
        )

        # user 2 can delete projects if user 2 has delete access
        resp = await _delete_project(client, new_project)
        await assert_status(
            resp,
            expected_status_code=(
                expected.no_content if share_rights["delete"] else expected.forbidden
            ),
        )


@pytest.mark.parametrize(
    "user_role,expected, save_state",
    [
        (UserRole.ANONYMOUS, status.HTTP_401_UNAUTHORIZED, False),
        (UserRole.GUEST, status.HTTP_200_OK, False),
        (UserRole.USER, status.HTTP_200_OK, True),
        (UserRole.TESTER, status.HTTP_200_OK, True),
    ],
)
async def test_open_project(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    client_session_id_factory: Callable[[], str],
    expected: HTTPStatus,
    save_state: bool,
    mocked_director_v2_api: dict[str, mock.Mock],
    mock_service_resources: ServiceResourcesDict,
    mock_orphaned_services: mock.Mock,
    mock_catalog_api: dict[str, mock.Mock],
    osparc_product_name: str,
    mocked_notifications_plugin: dict[str, mock.Mock],
):
    # POST /v0/projects/{project_id}:open
    # open project
    assert client.app
    url = client.app.router["open_project"].url_for(project_id=user_project["uuid"])
    resp = await client.post(f"{url}", json=client_session_id_factory())

    await assert_status(resp, expected)

    if resp.status == status.HTTP_200_OK:
        # calls notifications to subscribe to this project
        mocked_notifications_plugin["subscribe"].assert_called_once_with(
            client.app, ProjectID(user_project["uuid"])
        )
        # calls all dynamic-services in project to start
        dynamic_services = {
            service_uuid: service
            for service_uuid, service in user_project["workbench"].items()
            if "/dynamic/" in service["key"]
        }
        calls = []
        request_scheme = resp.url.scheme
        request_dns = f"{resp.url.host}:{resp.url.port}"
        for service_uuid, service in dynamic_services.items():
            calls.append(
                call(
                    app=client.app,
                    dynamic_service_start=DynamicServiceStart(
                        project_id=user_project["uuid"],
                        service_key=service["key"],
                        service_uuid=service_uuid,
                        service_version=service["version"],
                        user_id=logged_user["id"],
                        request_scheme=request_scheme,
                        simcore_user_agent=UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE,
                        request_dns=request_dns,
                        can_save=save_state,
                        product_name=osparc_product_name,
                        service_resources=ServiceResourcesDictHelpers.create_jsonable(
                            mock_service_resources
                        ),
                        wallet_info=None,
                        pricing_info=None,
                        hardware_info=None,
                    ),
                )
            )
        mocked_director_v2_api[
            "dynamic_scheduler.api.run_dynamic_service"
        ].assert_has_calls(calls)
    else:
        mocked_notifications_plugin["subscribe"].assert_not_called()


@pytest.mark.parametrize(
    "user_role,expected,save_state",
    [
        (UserRole.ANONYMOUS, status.HTTP_401_UNAUTHORIZED, False),
        (UserRole.GUEST, status.HTTP_403_FORBIDDEN, False),
        (UserRole.USER, status.HTTP_200_OK, True),
        (UserRole.TESTER, status.HTTP_200_OK, True),
    ],
)
async def test_open_template_project_for_edition(
    client: TestClient,
    logged_user: UserInfoDict,
    create_template_project: Callable[..., Awaitable[ProjectDict]],
    client_session_id_factory: Callable[[], str],
    expected: HTTPStatus,
    save_state: bool,
    mocked_director_v2_api: dict[str, mock.Mock],
    mock_service_resources: ServiceResourcesDict,
    mock_orphaned_services: mock.Mock,
    mock_catalog_api: dict[str, mock.Mock],
    osparc_product_name: str,
    mocked_notifications_plugin: dict[str, mock.Mock],
):
    # POST /v0/projects/{project_id}:open
    # open project
    assert client.app
    # NOTE: we need write access right to open a template
    template_project = await create_template_project(
        accessRights={
            logged_user["primary_gid"]: {"read": True, "write": True, "delete": False}
        }
    )
    url = client.app.router["open_project"].url_for(project_id=template_project["uuid"])
    resp = await client.post(f"{url}", json=client_session_id_factory())
    await assert_status(resp, expected)

    if resp.status == status.HTTP_200_OK:
        mocked_notifications_plugin["subscribe"].assert_called_once_with(
            client.app, ProjectID(template_project["uuid"])
        )
        dynamic_services = {
            service_uuid: service
            for service_uuid, service in template_project["workbench"].items()
            if "/dynamic/" in service["key"]
        }
        calls = []
        request_scheme = resp.url.scheme
        request_dns = f"{resp.url.host}:{resp.url.port}"
        for service_uuid, service in dynamic_services.items():
            calls.append(
                call(
                    app=client.app,
                    dynamic_service_start=DynamicServiceStart(
                        project_id=template_project["uuid"],
                        service_key=service["key"],
                        service_uuid=service_uuid,
                        service_version=service["version"],
                        user_id=logged_user["id"],
                        request_scheme=request_scheme,
                        simcore_user_agent=UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE,
                        request_dns=request_dns,
                        can_save=save_state,
                        service_resources=ServiceResourcesDictHelpers.create_jsonable(
                            mock_service_resources
                        ),
                        product_name=osparc_product_name,
                        wallet_info=None,
                        pricing_info=None,
                        hardware_info=None,
                    ),
                )
            )
        mocked_director_v2_api[
            "dynamic_scheduler.api.run_dynamic_service"
        ].assert_has_calls(calls)
    else:
        mocked_notifications_plugin["subscribe"].assert_not_called()


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.ANONYMOUS, status.HTTP_401_UNAUTHORIZED),
        (UserRole.GUEST, status.HTTP_403_FORBIDDEN),
        (UserRole.USER, status.HTTP_403_FORBIDDEN),
        (UserRole.TESTER, status.HTTP_403_FORBIDDEN),
    ],
)
async def test_open_template_project_for_edition_with_missing_write_rights(
    client: TestClient,
    logged_user: UserInfoDict,
    create_template_project: Callable[..., Awaitable[ProjectDict]],
    client_session_id_factory: Callable[[], str],
    expected: HTTPStatus,
    mocked_director_v2_api: dict[str, mock.Mock],
    mock_service_resources: ServiceResourcesDict,
    mock_orphaned_services: mock.Mock,
    mock_catalog_api: dict[str, mock.Mock],
):
    # POST /v0/projects/{project_id}:open
    # open project
    assert client.app
    # NOTE: we need write access right to open a template
    template_project = await create_template_project(
        accessRights={
            logged_user["primary_gid"]: {"read": True, "write": False, "delete": True}
        }
    )
    url = client.app.router["open_project"].url_for(project_id=template_project["uuid"])
    resp = await client.post(f"{url}", json=client_session_id_factory())
    await assert_status(resp, expected)


def standard_user_role() -> tuple[str, tuple]:
    all_roles = standard_role_response()

    return (all_roles[0], (pytest.param(*all_roles[1][2], id="standard user role"),))


@pytest.mark.parametrize(*standard_user_role())
async def test_open_project_with_small_amount_of_dynamic_services_starts_them_automatically(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project_with_num_dynamic_services: Callable[[int], Awaitable[ProjectDict]],
    client_session_id_factory: Callable,
    expected: ExpectedResponse,
    mocked_director_v2_api: dict[str, mock.Mock],
    mock_catalog_api: dict[str, mock.Mock],
    max_amount_of_auto_started_dyn_services: int,
    faker: Faker,
    mocked_notifications_plugin: dict[str, mock.Mock],
    create_dynamic_service_mock: Callable[..., Awaitable[DynamicServiceGet]],
):
    assert client.app
    num_of_dyn_services = max_amount_of_auto_started_dyn_services
    project = await user_project_with_num_dynamic_services(num_of_dyn_services)
    all_service_uuids = list(project["workbench"])
    num_service_already_running = faker.pyint(
        min_value=1, max_value=num_of_dyn_services - 1
    )
    assert num_service_already_running < num_of_dyn_services
    _ = [
        await create_dynamic_service_mock(
            user_id=logged_user["id"],
            project_id=project["uuid"],
            service_uuid=all_service_uuids[service_id],
        )
        for service_id in range(num_service_already_running)
    ]

    url = client.app.router["open_project"].url_for(project_id=project["uuid"])
    resp = await client.post(f"{url}", json=client_session_id_factory())
    await assert_status(resp, expected.ok)
    mocked_notifications_plugin["subscribe"].assert_called_once_with(
        client.app, ProjectID(project["uuid"])
    )
    mocked_notifications_plugin["subscribe"].reset_mock()
    assert mocked_director_v2_api[
        "dynamic_scheduler.api.run_dynamic_service"
    ].call_count == (num_of_dyn_services - num_service_already_running)
    mocked_director_v2_api["dynamic_scheduler.api.run_dynamic_service"].reset_mock()


@pytest.mark.parametrize(*standard_user_role())
async def test_open_project_with_disable_service_auto_start_set_overrides_behavior(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project_with_num_dynamic_services: Callable[[int], Awaitable[ProjectDict]],
    client_session_id_factory: Callable,
    expected: ExpectedResponse,
    mocked_director_v2_api: dict[str, mock.Mock],
    mock_catalog_api: dict[str, mock.Mock],
    max_amount_of_auto_started_dyn_services: int,
    faker: Faker,
    mocked_notifications_plugin: dict[str, mock.Mock],
):
    assert client.app
    num_of_dyn_services = max_amount_of_auto_started_dyn_services or faker.pyint(
        min_value=3, max_value=250
    )
    project = await user_project_with_num_dynamic_services(num_of_dyn_services)
    all_service_uuids = list(project["workbench"])
    for num_service_already_running in range(num_of_dyn_services):
        mocked_director_v2_api["director_v2.api.list_dynamic_services"].return_value = [
            {"service_uuid": all_service_uuids[service_id]}
            for service_id in range(num_service_already_running)
        ]

        url = (
            client.app.router["open_project"]
            .url_for(project_id=project["uuid"])
            .with_query(disable_service_auto_start=f"{True}")
        )

        resp = await client.post(f"{url}", json=client_session_id_factory())
        await assert_status(resp, expected.ok)
        mocked_notifications_plugin["subscribe"].assert_called_once_with(
            client.app, ProjectID(project["uuid"])
        )
        mocked_notifications_plugin["subscribe"].reset_mock()
        mocked_director_v2_api[
            "dynamic_scheduler.api.run_dynamic_service"
        ].assert_not_called()


@pytest.mark.parametrize(*standard_user_role())
async def test_open_project_with_large_amount_of_dynamic_services_does_not_start_them_automatically(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project_with_num_dynamic_services: Callable[[int], Awaitable[ProjectDict]],
    client_session_id_factory: Callable,
    expected: ExpectedResponse,
    mocked_director_v2_api: dict[str, mock.Mock],
    mock_catalog_api: dict[str, mock.Mock],
    max_amount_of_auto_started_dyn_services: int,
    mocked_notifications_plugin: dict[str, mock.Mock],
    create_dynamic_service_mock: Callable[..., Awaitable[DynamicServiceGet]],
    faker: Faker,
):
    assert client.app

    project = await user_project_with_num_dynamic_services(
        max_amount_of_auto_started_dyn_services + 1
    )
    all_service_uuids = list(project["workbench"])
    num_service_already_running = faker.pyint(
        min_value=0, max_value=max_amount_of_auto_started_dyn_services
    )
    assert num_service_already_running <= max_amount_of_auto_started_dyn_services
    _ = [
        await create_dynamic_service_mock(
            user_id=logged_user["id"],
            project_id=project["uuid"],
            service_uuid=all_service_uuids[service_id],
        )
        for service_id in range(num_service_already_running)
    ]

    url = client.app.router["open_project"].url_for(project_id=project["uuid"])
    resp = await client.post(f"{url}", json=client_session_id_factory())
    await assert_status(resp, expected.ok)
    mocked_notifications_plugin["subscribe"].assert_called_once_with(
        client.app, ProjectID(project["uuid"])
    )
    mocked_notifications_plugin["subscribe"].reset_mock()
    mocked_director_v2_api[
        "dynamic_scheduler.api.run_dynamic_service"
    ].assert_not_called()


@pytest.mark.parametrize(*standard_user_role())
async def test_open_project_with_large_amount_of_dynamic_services_starts_them_if_setting_disabled(
    mock_get_total_project_dynamic_nodes_creation_interval: None,
    disable_max_number_of_running_dynamic_nodes: dict[str, str],
    client: TestClient,
    logged_user: UserInfoDict,
    user_project_with_num_dynamic_services: Callable[[int], Awaitable[ProjectDict]],
    client_session_id_factory: Callable,
    expected: ExpectedResponse,
    mocked_director_v2_api: dict[str, mock.Mock],
    mock_catalog_api: dict[str, mock.Mock],
    max_amount_of_auto_started_dyn_services: int,
    faker: Faker,
    mocked_notifications_plugin: dict[str, mock.Mock],
    create_dynamic_service_mock: Callable[..., Awaitable[DynamicServiceGet]],
):
    assert client.app
    assert max_amount_of_auto_started_dyn_services == 0, "setting not disabled!"
    # NOTE: reduced the amount of services in the test:
    # - services start in a sequence with  a lock
    # - lock is a bit slower to acquire and release then without the non locking version
    # 20 services ~ 55 second runtime
    num_of_dyn_services = 7
    project = await user_project_with_num_dynamic_services(num_of_dyn_services + 1)
    all_service_uuids = list(project["workbench"])
    num_service_already_running = faker.pyint(
        min_value=0, max_value=num_of_dyn_services
    )
    assert num_service_already_running <= num_of_dyn_services
    _ = [
        await create_dynamic_service_mock(
            user_id=logged_user["id"],
            project_id=project["uuid"],
            service_uuid=all_service_uuids[service_id],
        )
        for service_id in range(num_service_already_running)
    ]

    url = client.app.router["open_project"].url_for(project_id=project["uuid"])
    resp = await client.post(f"{url}", json=client_session_id_factory())
    await assert_status(resp, expected.ok)
    mocked_notifications_plugin["subscribe"].assert_called_once_with(
        client.app, ProjectID(project["uuid"])
    )
    mocked_notifications_plugin["subscribe"].reset_mock()
    mocked_director_v2_api["dynamic_scheduler.api.run_dynamic_service"].assert_called()


@pytest.mark.parametrize(*standard_user_role())
async def test_open_project_with_deprecated_services_ok_but_does_not_start_dynamic_services(
    client: TestClient,
    logged_user,
    user_project,
    client_session_id_factory: Callable,
    expected: ExpectedResponse,
    mocked_director_v2_api: dict[str, mock.Mock],
    mock_service_resources: ServiceResourcesDict,
    mock_orphaned_services,
    mock_catalog_api: dict[str, mock.Mock],
    mocked_notifications_plugin: dict[str, mock.Mock],
):
    mock_catalog_api["get_service"].return_value["deprecated"] = (
        datetime.now(UTC) - timedelta(days=1)
    ).isoformat()
    url = client.app.router["open_project"].url_for(project_id=user_project["uuid"])
    resp = await client.post(url, json=client_session_id_factory())
    await assert_status(resp, expected.ok)
    mocked_notifications_plugin["subscribe"].assert_called_once_with(
        client.app, ProjectID(user_project["uuid"])
    )
    mocked_director_v2_api[
        "dynamic_scheduler.api.run_dynamic_service"
    ].assert_not_called()


@pytest.fixture
def one_max_open_studies_per_user(
    postgres_db: sa.engine.Engine, osparc_product_name: str
) -> Iterator[None]:
    with postgres_db.connect() as conn:
        old_value = conn.scalar(
            sa.select(products.c.max_open_studies_per_user).where(
                products.c.name == osparc_product_name
            )
        )
        conn.execute(
            products.update()
            .values(max_open_studies_per_user=1)
            .where(products.c.name == osparc_product_name)
        )
    yield

    with postgres_db.connect() as conn:
        conn.execute(
            products.update()
            .values(max_open_studies_per_user=old_value)
            .where(products.c.name == osparc_product_name)
        )


@pytest.mark.parametrize(*standard_role_response())
async def test_open_project_more_than_limitation_of_max_studies_open_per_user(
    one_max_open_studies_per_user: None,
    client: TestClient,
    logged_user,
    client_session_id_factory: Callable,
    user_project: ProjectDict,
    shared_project: ProjectDict,
    expected: ExpectedResponse,
    mocked_director_v2_api: dict[str, mock.Mock],
    mock_catalog_api: dict[str, mock.Mock],
    user_role: UserRole,
    mocked_notifications_plugin: dict[str, mock.Mock],
):
    client_id_1 = client_session_id_factory()
    await _open_project(
        client,
        client_id_1,
        user_project,
        expected.ok if user_role != UserRole.GUEST else status.HTTP_200_OK,
    )

    client_id_2 = client_session_id_factory()
    await _open_project(
        client,
        client_id_2,
        shared_project,
        expected.conflict if user_role != UserRole.GUEST else status.HTTP_409_CONFLICT,
    )


@pytest.mark.parametrize(*standard_role_response())
async def test_close_project(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    client_session_id_factory: Callable,
    expected,
    mocked_director_v2_api: dict[str, mock.Mock],
    mock_catalog_api: dict[str, mock.Mock],
    fake_services: Callable[..., Awaitable[list[DynamicServiceGet]]],
    mock_dynamic_scheduler_rabbitmq: None,
    mocked_notifications_plugin: dict[str, mock.Mock],
):
    # POST /v0/projects/{project_id}:close
    fake_dynamic_services = await fake_services(number_services=5)
    assert len(fake_dynamic_services) == 5
    mocked_director_v2_api[
        "dynamic_scheduler.api.list_dynamic_services"
    ].return_value = fake_dynamic_services

    user_id = logged_user["id"]

    assert client.app
    # open project
    client_id = client_session_id_factory()
    url = client.app.router["open_project"].url_for(project_id=user_project["uuid"])
    resp = await client.post(f"{url}", json=client_id)

    if resp.status == status.HTTP_200_OK:
        mocked_notifications_plugin["subscribe"].assert_called_once_with(
            client.app, ProjectID(user_project["uuid"])
        )
        mocked_director_v2_api["director_v2.api.list_dynamic_services"].assert_any_call(
            client.app, user_id, user_project["uuid"]
        )
        mocked_director_v2_api["director_v2.api.list_dynamic_services"].reset_mock()
    else:
        mocked_notifications_plugin["subscribe"].assert_not_called()

    # close project
    url = client.app.router["close_project"].url_for(project_id=user_project["uuid"])
    resp = await client.post(f"{url}", json=client_id)
    await assert_status(resp, expected.no_content)

    if resp.status == status.HTTP_204_NO_CONTENT:
        mocked_notifications_plugin["unsubscribe"].assert_called_once_with(
            client.app, ProjectID(user_project["uuid"])
        )
        # These checks are after a fire&forget, so we wait a moment
        await asyncio.sleep(2)

        calls = [
            call(
                client.app,
                user_id=user_id,
                project_id=user_project["uuid"],
            ),
        ]
        mocked_director_v2_api[
            "dynamic_scheduler.api.list_dynamic_services"
        ].assert_has_calls(calls)

        calls = [
            call(
                app=client.app,
                dynamic_service_stop=DynamicServiceStop(
                    user_id=user_id,
                    project_id=service.project_id,
                    node_id=service.node_uuid,
                    simcore_user_agent=UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE,
                    save_state=True,
                ),
                progress=mock.ANY,
            )
            for service in fake_dynamic_services
        ]
        mocked_director_v2_api[
            "dynamic_scheduler.api.stop_dynamic_service"
        ].assert_has_calls(calls)

        # should not be callsed request_retrieve_dyn_service


@pytest.mark.parametrize(
    "user_role, expected",
    [
        (UserRole.ANONYMOUS, status.HTTP_401_UNAUTHORIZED),
        (UserRole.GUEST, status.HTTP_200_OK),
        (UserRole.USER, status.HTTP_200_OK),
        (UserRole.TESTER, status.HTTP_200_OK),
    ],
)
async def test_get_active_project(
    client: TestClient,
    logged_user,
    user_project,
    client_session_id_factory: Callable,
    expected,
    socketio_client_factory: Callable,
    mocked_director_v2_api: dict[str, mock.Mock],
    mock_catalog_api: dict[str, mock.Mock],
    mocked_notifications_plugin: dict[str, mock.Mock],
):
    # login with socket using client session id
    client_id1 = client_session_id_factory()
    sio = None
    try:
        sio = await socketio_client_factory(client_id1)
        assert sio.sid
    except SocketConnectionError:
        if expected == status.HTTP_200_OK:
            pytest.fail("socket io connection should not fail")
    assert client.app
    # get active projects -> empty
    get_active_projects_url = (
        client.app.router["get_active_project"]
        .url_for()
        .with_query(client_session_id=client_id1)
    )
    resp = await client.get(f"{get_active_projects_url}")
    data, error = await assert_status(resp, expected)
    if resp.status == status.HTTP_200_OK:
        assert not data
        assert not error

    # open project
    open_project_url = client.app.router["open_project"].url_for(
        project_id=user_project["uuid"]
    )
    resp = await client.post(f"{open_project_url}", json=client_id1)
    await assert_status(resp, expected)

    resp = await client.get(f"{get_active_projects_url}")
    data, error = await assert_status(resp, expected)
    if resp.status == status.HTTP_200_OK:
        mocked_notifications_plugin["subscribe"].assert_called_once_with(
            client.app, ProjectID(user_project["uuid"])
        )
        assert not error
        assert ProjectState(**data.pop("state")).locked.value
        data.pop("folderId")

        user_project_last_change_date = user_project.pop("lastChangeDate")
        data_last_change_date = data.pop("lastChangeDate")
        assert user_project_last_change_date < data_last_change_date

        assert data == {k: user_project[k] for k in data}
    else:
        mocked_notifications_plugin["subscribe"].assert_not_called()

    # login with socket using client session id2
    client_id2 = client_session_id_factory()
    try:
        sio = await socketio_client_factory(client_id2)
        assert sio.sid
    except SocketConnectionError:
        if expected == status.HTTP_200_OK:
            pytest.fail("socket io connection should not fail")
    # get active projects -> empty
    get_active_projects_url = (
        client.app.router["get_active_project"]
        .url_for()
        .with_query(client_session_id=client_id2)
    )
    resp = await client.get(f"{get_active_projects_url}")
    data, error = await assert_status(resp, expected)
    if resp.status == status.HTTP_200_OK:
        assert not data
        assert not error


@pytest.mark.parametrize(
    "user_role, expected_response_on_create, expected_response_on_get, expected_response_on_delete",
    [
        (
            UserRole.USER,
            status.HTTP_201_CREATED,
            status.HTTP_200_OK,
            status.HTTP_204_NO_CONTENT,
        ),
        (
            UserRole.TESTER,
            status.HTTP_201_CREATED,
            status.HTTP_200_OK,
            status.HTTP_204_NO_CONTENT,
        ),
    ],
)
async def test_project_node_lifetime(  # noqa: PLR0915
    client: TestClient,
    logged_user: UserInfoDict,
    user_project,
    expected_response_on_create,
    expected_response_on_get,
    expected_response_on_delete,
    mocked_director_v2_api: dict[str, mock.Mock],
    storage_subsystem_mock,
    mock_catalog_api: dict[str, mock.Mock],
    mocker,
    faker: Faker,
    create_dynamic_service_mock: Callable[..., Awaitable[DynamicServiceGet]],
):
    mock_storage_api_delete_data_folders_of_project_node = mocker.patch(
        "simcore_service_webserver.projects._crud_handlers.projects_api.storage_api.delete_data_folders_of_project_node",
        return_value="",
    )
    assert client.app

    # create a new dynamic node...
    url = client.app.router["create_node"].url_for(project_id=user_project["uuid"])
    body = {
        "service_key": "simcore/services/dynamic/key",
        "service_version": "1.3.4",
        "service_id": None,
    }
    resp = await client.post(url.path, json=body)
    data, errors = await assert_status(resp, expected_response_on_create)
    dynamic_node_id = None
    if resp.status == status.HTTP_201_CREATED:
        mocked_director_v2_api[
            "dynamic_scheduler.api.run_dynamic_service"
        ].assert_called_once()
        assert "node_id" in data
        dynamic_node_id = data["node_id"]
    else:
        mocked_director_v2_api[
            "dynamic_scheduler.api.run_dynamic_service"
        ].assert_not_called()

    # create a new NOT dynamic node...
    mocked_director_v2_api["dynamic_scheduler.api.run_dynamic_service"].reset_mock()
    url = client.app.router["create_node"].url_for(project_id=user_project["uuid"])
    body = {
        "service_key": "simcore/services/comp/key",
        "service_version": "1.3.4",
        "service_id": None,
    }
    resp = await client.post(f"{url}", json=body)
    data, errors = await assert_status(resp, expected_response_on_create)
    computational_node_id = None
    if resp.status == status.HTTP_201_CREATED:
        mocked_director_v2_api[
            "dynamic_scheduler.api.run_dynamic_service"
        ].assert_not_called()
        assert "node_id" in data
        computational_node_id = data["node_id"]
    else:
        mocked_director_v2_api[
            "dynamic_scheduler.api.run_dynamic_service"
        ].assert_not_called()

    # get the node state
    _created_dynamic_service_mock = await create_dynamic_service_mock(
        user_id=logged_user["id"],
        project_id=user_project["uuid"],
        service_uuid=dynamic_node_id,
        service_state=ServiceState.RUNNING,
    )
    assert dynamic_node_id
    url = client.app.router["get_node"].url_for(
        project_id=user_project["uuid"], node_id=dynamic_node_id
    )

    node_sample = deepcopy(NodeGet.model_config["json_schema_extra"]["examples"][1])
    mocked_director_v2_api[
        "dynamic_scheduler.api.get_dynamic_service"
    ].return_value = NodeGet.model_validate(
        {
            **node_sample,
            "service_state": "running",
        }
    )
    resp = await client.get(f"{url}")
    data, errors = await assert_status(resp, expected_response_on_get)
    if resp.status == status.HTTP_200_OK:
        assert "service_state" in data
        assert data["service_state"] == "running"

    # get the NOT dynamic node state
    assert computational_node_id
    url = client.app.router["get_node"].url_for(
        project_id=user_project["uuid"], node_id=computational_node_id
    )
    mocked_director_v2_api[
        "dynamic_scheduler.api.get_dynamic_service"
    ].return_value = NodeGetIdle.model_validate(
        {
            "service_uuid": node_sample["service_uuid"],
            "service_state": "idle",
        }
    )
    resp = await client.get(f"{url}")
    data, errors = await assert_status(resp, expected_response_on_get)
    if resp.status == status.HTTP_200_OK:
        assert "service_state" in data
        assert data["service_state"] == "idle"

    # delete the node
    url = client.app.router["delete_node"].url_for(
        project_id=user_project["uuid"], node_id=dynamic_node_id
    )
    resp = await client.delete(f"{url}")
    data, errors = await assert_status(resp, expected_response_on_delete)
    await asyncio.sleep(5)
    if resp.status == status.HTTP_204_NO_CONTENT:
        mocked_director_v2_api[
            "dynamic_scheduler.api.stop_dynamic_service"
        ].assert_called_once()
        mock_storage_api_delete_data_folders_of_project_node.assert_called_once()
    else:
        mocked_director_v2_api[
            "dynamic_scheduler.api.stop_dynamic_service"
        ].assert_not_called()
        mock_storage_api_delete_data_folders_of_project_node.assert_not_called()

    # delete the NOT dynamic node
    mocked_director_v2_api["dynamic_scheduler.api.stop_dynamic_service"].reset_mock()
    mock_storage_api_delete_data_folders_of_project_node.reset_mock()
    url = client.app.router["delete_node"].url_for(
        project_id=user_project["uuid"], node_id=computational_node_id
    )
    resp = await client.delete(f"{url}")
    data, errors = await assert_status(resp, expected_response_on_delete)
    if resp.status == status.HTTP_204_NO_CONTENT:
        mocked_director_v2_api[
            "dynamic_scheduler.api.stop_dynamic_service"
        ].assert_not_called()
        mock_storage_api_delete_data_folders_of_project_node.assert_called_once()
    else:
        mocked_director_v2_api[
            "dynamic_scheduler.api.stop_dynamic_service"
        ].assert_not_called()
        mock_storage_api_delete_data_folders_of_project_node.assert_not_called()


@pytest.fixture
def client_on_running_server_factory(
    client: TestClient, event_loop
) -> Iterator[Callable]:
    # Creates clients connected to the same server as the reference client
    #
    # Implemented as aihttp_client but creates a client using a running server,
    #  i.e. avoid client.start_server

    assert isinstance(client.server, TestServer)

    clients = []

    def go():
        cli = TestClient(client.server, loop=event_loop)
        assert client.server.started
        # AVOIDS client.start_server
        clients.append(cli)
        return cli

    yield go

    async def close_client_but_not_server(cli: TestClient):
        # pylint: disable=protected-access
        if not cli._closed:  # noqa: SLF001
            for resp in cli._responses:  # noqa: SLF001
                resp.close()
            for ws in cli._websockets:  # noqa: SLF001
                await ws.close()
            await cli._session.close()  # noqa: SLF001
            cli._closed = True  # noqa: SLF001

    async def finalize():
        while clients:
            await close_client_but_not_server(clients.pop())

    event_loop.run_until_complete(finalize())


@pytest.fixture
def clean_redis_table(redis_client) -> None:
    """this just ensures the redis table is cleaned up between test runs"""


@pytest.mark.parametrize(*standard_role_response())
async def test_open_shared_project_2_users_locked(
    client: TestClient,
    client_on_running_server_factory: Callable,
    logged_user: dict,
    shared_project: dict,
    socketio_client_factory: Callable,
    client_session_id_factory: Callable,
    user_role: UserRole,
    expected: ExpectedResponse,
    mocker,
    mocked_director_v2_api: dict[str, mock.Mock],
    mock_orphaned_services,
    mock_catalog_api: dict[str, mock.Mock],
    clean_redis_table: None,
    mock_dynamic_scheduler_rabbitmq: None,
    mocked_notifications_plugin: dict[str, mock.Mock],
):
    # Use-case: user 1 opens a shared project, user 2 tries to open it as well
    mock_project_state_updated_handler = mocker.Mock()

    client_1 = client
    client_id1 = client_session_id_factory()
    client_2 = client_on_running_server_factory()
    client_id2 = client_session_id_factory()

    # 1. user 1 opens project
    await _connect_websocket(
        socketio_client_factory,
        user_role != UserRole.ANONYMOUS,
        client_1,
        client_id1,
        {SOCKET_IO_PROJECT_UPDATED_EVENT: mock_project_state_updated_handler},
    )
    # expected is that the project is closed and unlocked
    expected_project_state_client_1 = ProjectState(
        locked=ProjectLocked(value=False, status=ProjectStatus.CLOSED),
        state=ProjectRunningState(value=RunningState.NOT_STARTED),
    )
    for _client_id in [client_id1, None]:
        await _state_project(
            client_1,
            shared_project,
            expected.ok if user_role != UserRole.GUEST else status.HTTP_200_OK,
            expected_project_state_client_1,
        )
    await _open_project(
        client_1,
        client_id1,
        shared_project,
        expected.ok if user_role != UserRole.GUEST else status.HTTP_200_OK,
    )
    # now the expected result is that the project is locked and opened by client 1
    owner1 = Owner(
        user_id=logged_user["id"],
        first_name=logged_user.get("first_name", None),
        last_name=logged_user.get("last_name", None),
    )
    expected_project_state_client_1.locked.value = True
    expected_project_state_client_1.locked.status = ProjectStatus.OPENED
    expected_project_state_client_1.locked.owner = owner1
    # NOTE: there are 2 calls since we are part of the primary group and the all group
    await _assert_project_state_updated(
        mock_project_state_updated_handler,
        shared_project,
        [expected_project_state_client_1]
        * (0 if user_role == UserRole.ANONYMOUS else 2),
    )
    await _state_project(
        client_1,
        shared_project,
        expected.ok if user_role != UserRole.GUEST else status.HTTP_200_OK,
        expected_project_state_client_1,
    )

    # 2. create a separate client now and log in user2, try to open the same shared project
    user_2 = await log_client_in(
        client_2, {"role": user_role.name}, enable_check=user_role != UserRole.ANONYMOUS
    )
    await _connect_websocket(
        socketio_client_factory,
        user_role != UserRole.ANONYMOUS,
        client_2,
        client_id2,
        {SOCKET_IO_PROJECT_UPDATED_EVENT: mock_project_state_updated_handler},
    )
    await _open_project(
        client_2,
        client_id2,
        shared_project,
        expected.locked if user_role != UserRole.GUEST else status.HTTP_423_LOCKED,
    )
    expected_project_state_client_2 = deepcopy(expected_project_state_client_1)
    expected_project_state_client_2.locked.status = ProjectStatus.OPENED

    await _state_project(
        client_2,
        shared_project,
        expected.ok if user_role != UserRole.GUEST else status.HTTP_200_OK,
        expected_project_state_client_2,
    )

    # 3. user 1 closes the project
    await _close_project(client_1, client_id1, shared_project, expected.no_content)
    if not any(user_role == role for role in [UserRole.ANONYMOUS, UserRole.GUEST]):
        # Guests cannot close projects
        expected_project_state_client_1 = ProjectState(
            locked=ProjectLocked(value=False, status=ProjectStatus.CLOSED),
            state=ProjectRunningState(value=RunningState.NOT_STARTED),
        )

    # we should receive an event that the project lock state changed
    # NOTE: there are 2x3 calls since we are part of the primary group and the all group and user 2 is part of the all group
    # first CLOSING, then CLOSED
    await _assert_project_state_updated(
        mock_project_state_updated_handler,
        shared_project,
        [
            expected_project_state_client_1.model_copy(
                update={
                    "locked": ProjectLocked(
                        value=True, status=ProjectStatus.CLOSING, owner=owner1
                    )
                }
            )
        ]
        * (
            0
            if any(user_role == role for role in [UserRole.ANONYMOUS, UserRole.GUEST])
            else 3
        )
        + [expected_project_state_client_1]
        * (
            0
            if any(user_role == role for role in [UserRole.ANONYMOUS, UserRole.GUEST])
            else 3
        ),
    )
    await _state_project(
        client_1,
        shared_project,
        expected.ok if user_role != UserRole.GUEST else status.HTTP_200_OK,
        expected_project_state_client_1,
    )

    # 4. user 2 now should be able to open the project
    await _open_project(
        client_2,
        client_id2,
        shared_project,
        expected.ok if user_role != UserRole.GUEST else status.HTTP_423_LOCKED,
    )
    if not any(user_role == role for role in [UserRole.ANONYMOUS, UserRole.GUEST]):
        expected_project_state_client_2.locked.value = True
        expected_project_state_client_2.locked.status = ProjectStatus.OPENED
        owner2 = Owner(
            user_id=PositiveInt(user_2["id"]),
            first_name=user_2.get("first_name", None),
            last_name=user_2.get("last_name", None),
        )
        expected_project_state_client_2.locked.owner = owner2
        expected_project_state_client_1.locked.value = True
        expected_project_state_client_1.locked.status = ProjectStatus.OPENED
        expected_project_state_client_1.locked.owner = owner2
    # NOTE: there are 3 calls since we are part of the primary group and the all group
    await _assert_project_state_updated(
        mock_project_state_updated_handler,
        shared_project,
        [expected_project_state_client_1]
        * (
            0
            if any(user_role == role for role in [UserRole.ANONYMOUS, UserRole.GUEST])
            else 3
        ),
    )
    await _state_project(
        client_1,
        shared_project,
        expected.ok if user_role != UserRole.GUEST else status.HTTP_200_OK,
        expected_project_state_client_1,
    )


@pytest.mark.parametrize(*standard_role_response())
async def test_open_shared_project_at_same_time(
    client: TestClient,
    client_on_running_server_factory: Callable,
    logged_user: dict,
    shared_project: dict,
    socketio_client_factory: Callable,
    client_session_id_factory: Callable,
    user_role: UserRole,
    expected: ExpectedResponse,
    mocked_director_v2_api: dict[str, mock.Mock],
    mock_orphaned_services,
    mock_catalog_api: dict[str, mock.Mock],
    clean_redis_table,
    mock_dynamic_scheduler_rabbitmq: None,
    mocked_notifications_plugin: dict[str, mock.Mock],
):
    NUMBER_OF_ADDITIONAL_CLIENTS = 10
    # log client 1
    client_1 = client
    client_id1 = client_session_id_factory()
    sio_1 = await _connect_websocket(
        socketio_client_factory,
        user_role != UserRole.ANONYMOUS,
        client_1,
        client_id1,
    )
    clients = [
        {"client": client_1, "user": logged_user, "client_id": client_id1, "sio": sio_1}
    ]
    # create other clients
    for _i in range(NUMBER_OF_ADDITIONAL_CLIENTS):
        new_client = client_on_running_server_factory()
        user = await log_client_in(
            new_client,
            {"role": user_role.name},
            enable_check=user_role != UserRole.ANONYMOUS,
        )
        client_id = client_session_id_factory()
        sio = await _connect_websocket(
            socketio_client_factory,
            user_role != UserRole.ANONYMOUS,
            new_client,
            client_id,
        )
        clients.append(
            {"client": new_client, "user": user, "client_id": client_id, "sio": sio}
        )

    # try opening projects at same time (more or less)
    open_project_tasks = [
        _open_project(
            c["client"],
            c["client_id"],
            shared_project,
            [
                expected.ok if user_role != UserRole.GUEST else status.HTTP_200_OK,
                (
                    expected.locked
                    if user_role != UserRole.GUEST
                    else status.HTTP_423_LOCKED
                ),
            ],
        )
        for c in clients
    ]
    results = await asyncio.gather(
        *open_project_tasks,
        return_exceptions=True,
    )

    # one should be opened, the other locked
    if user_role != UserRole.ANONYMOUS:
        num_assertions = 0
        for data, error in results:
            assert data or error
            if error:
                num_assertions += 1
            elif data:
                project_status = ProjectState(**data.pop("state"))
                data.pop("folderId")
                assert data == shared_project
                assert project_status.locked.value
                assert project_status.locked.owner
                assert project_status.locked.owner.first_name in [
                    c["user"]["first_name"] for c in clients
                ]

        assert num_assertions == NUMBER_OF_ADDITIONAL_CLIENTS


@pytest.mark.parametrize(*standard_role_response())
async def test_opened_project_can_still_be_opened_after_refreshing_tab(
    client: TestClient,
    logged_user: dict[str, Any],
    user_project: dict[str, Any],
    client_session_id_factory: Callable,
    socketio_client_factory: Callable,
    user_role: UserRole,
    expected: ExpectedResponse,
    mocked_director_v2_api: dict[str, mock.MagicMock],
    mock_orphaned_services,
    mock_catalog_api: dict[str, mock.Mock],
    clean_redis_table,
    mocked_notifications_plugin: dict[str, mock.Mock],
):
    """Simulating a refresh goes as follows:
    The user opens a project, then hit the F5 refresh page.
    The browser disconnects the websocket, reconnects but the
    client_session_id remains the same
    """

    client_session_id = client_session_id_factory()
    sio = await _connect_websocket(
        socketio_client_factory,
        user_role != UserRole.ANONYMOUS,
        client,
        client_session_id,
    )
    assert client.app
    url = client.app.router["open_project"].url_for(project_id=user_project["uuid"])
    resp = await client.post(f"{url}", json=client_session_id)
    await assert_status(
        resp, expected.ok if user_role != UserRole.GUEST else status.HTTP_200_OK
    )
    if resp.status != status.HTTP_200_OK:
        return

    # the project is opened, now let's simulate a refresh
    assert sio
    await sio.disconnect()
    # give some time
    await asyncio.sleep(1)
    # re-connect using the same client session id
    sio2 = await _connect_websocket(
        socketio_client_factory,
        user_role != UserRole.ANONYMOUS,
        client,
        client_session_id,
    )
    assert sio2
    # re-open the project
    resp = await client.post(f"{url}", json=client_session_id)
    await assert_status(
        resp, expected.ok if user_role != UserRole.GUEST else status.HTTP_200_OK
    )
