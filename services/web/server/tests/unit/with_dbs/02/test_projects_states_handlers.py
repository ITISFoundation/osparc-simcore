# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=too-many-positional-arguments
# pylint: disable=too-many-statements
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from http import HTTPStatus
from typing import Any, TypedDict
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
from models_library.api_schemas_resource_usage_tracker.credit_transactions import (
    WalletTotalCredits,
)
from models_library.api_schemas_webserver.projects import (
    ProjectShareStateOutputSchema,
    ProjectStateOutputSchema,
)
from models_library.api_schemas_webserver.projects_nodes import NodeGet, NodeGetIdle
from models_library.groups import GroupID
from models_library.projects import ProjectID
from models_library.projects_state import (
    ProjectRunningState,
    ProjectStatus,
    RunningState,
)
from models_library.services_enums import ServiceState
from models_library.services_resources import (
    ServiceResourcesDict,
    ServiceResourcesDictHelpers,
)
from models_library.utils.fastapi_encoders import jsonable_encoder
from pydantic import TypeAdapter
from pytest_mock import MockerFixture
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.logging_tools import log_context
from pytest_simcore.helpers.webserver_login import LoggedUser, log_client_in
from pytest_simcore.helpers.webserver_parametrizations import (
    ExpectedResponse,
    standard_role_response,
    standard_user_role_response,
)
from pytest_simcore.helpers.webserver_projects import assert_get_same_project
from pytest_simcore.helpers.webserver_users import UserInfoDict
from servicelib.aiohttp import status
from servicelib.common_headers import UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE
from simcore_postgres_database.models.products import products
from simcore_postgres_database.models.wallets import wallets
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver.db.models import UserRole
from simcore_service_webserver.licenses._licensed_resources_service import DeepDiff
from simcore_service_webserver.projects.models import ProjectDict
from simcore_service_webserver.socketio.messages import SOCKET_IO_PROJECT_UPDATED_EVENT
from simcore_service_webserver.utils import to_datetime
from socketio.exceptions import ConnectionError as SocketConnectionError
from tenacity import (
    RetryError,
    before_sleep_log,
    retry,
    retry_if_exception_type,
    retry_unless_exception_type,
    stop_after_delay,
    wait_fixed,
)

RESOURCE_NAME = "projects"
API_PREFIX = f"/{API_VTAG}"


def assert_replaced(current_project, update_data):
    def _extract(dikt, keys):
        return {k: dikt[k] for k in keys}

    skip = [
        "lastChangeDate",
        "templateType",
        "trashedAt",
        "trashedBy",
        "workspaceId",
        "folderId",
    ]
    keep = [k for k in update_data if k not in skip]

    assert _extract(current_project, keep) == _extract(update_data, keep)

    k = "lastChangeDate"
    assert to_datetime(update_data[k]) < to_datetime(current_project[k])


async def _list_projects(
    client: TestClient,
    expected: int,
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
    assert isinstance(data, list)
    return data


async def _replace_project(
    client: TestClient, project_update: ProjectDict, expected: int
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


class _SocketHandlers(TypedDict):
    SOCKET_IO_PROJECT_UPDATED_EVENT: mock.Mock


@pytest.fixture
async def create_socketio_connection_with_handlers(
    create_socketio_connection: Callable[
        [TestClient | None], Awaitable[tuple[socketio.AsyncClient, str]]
    ],
    mocker: MockerFixture,
) -> Callable[
    [TestClient], Awaitable[tuple[socketio.AsyncClient, str, _SocketHandlers]]
]:
    async def _(
        client: TestClient,
    ) -> tuple[socketio.AsyncClient, str, _SocketHandlers]:
        sio, received_client_id = await create_socketio_connection(None, client)
        assert sio.sid

        event_handlers = _SocketHandlers(
            **{SOCKET_IO_PROJECT_UPDATED_EVENT: mocker.Mock()}
        )

        for event, handler in event_handlers.items():
            sio.on(event, handler=handler)
        return sio, received_client_id, event_handlers

    return _


async def _open_project(
    client: TestClient,
    client_id: str,
    project: ProjectDict,
    expected: int | list[int],
) -> tuple[dict, dict]:
    assert client.app

    url = client.app.router["open_project"].url_for(project_id=project["uuid"])
    resp = await client.post(f"{url}", json=client_id)

    if isinstance(expected, list):
        for e in expected:
            try:
                data, error = await assert_status(resp, e)
                return data, error
            except AssertionError:
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
    client: TestClient, client_id: str, project: dict, expected: int
):
    assert client.app

    url = client.app.router["close_project"].url_for(project_id=project["uuid"])
    resp = await client.post(f"{url}", json=client_id)
    await assert_status(resp, expected)


async def _state_project(
    client: TestClient,
    project: dict,
    expected: int,
    expected_project_state: ProjectStateOutputSchema,
):
    assert client.app

    url = client.app.router["get_project_state"].url_for(project_id=project["uuid"])
    resp = await client.get(f"{url}")
    data, error = await assert_status(resp, expected)
    if not error:
        received_state = ProjectStateOutputSchema(**data)
        assert received_state == expected_project_state


async def _assert_project_state_updated(
    handler: mock.Mock,
    shared_project: dict,
    expected_project_state_updates: list[ProjectStateOutputSchema],
) -> None:
    with log_context(logging.INFO, "assert_project_state_updated") as ctx:

        @retry(
            wait=wait_fixed(1),
            stop=stop_after_delay(15),
            retry=retry_if_exception_type(AssertionError),
            reraise=True,
            before_sleep=before_sleep_log(ctx.logger, logging.INFO),
        )
        async def _received_project_update_event() -> None:
            assert handler.call_count == len(
                expected_project_state_updates
            ), f"received {handler.call_count}:{handler.call_args_list} of {len(expected_project_state_updates)} expected calls"
            if expected_project_state_updates:
                calls = [
                    call(
                        jsonable_encoder(
                            {
                                "project_uuid": shared_project["uuid"],
                                "data": p_state.model_dump(
                                    by_alias=True, exclude_unset=True
                                ),
                            }
                        )
                    )
                    for p_state in expected_project_state_updates
                ]
                handler.assert_has_calls(calls)
                handler.reset_mock()

        if not expected_project_state_updates:
            with contextlib.suppress(RetryError):
                await _received_project_update_event.retry_with(
                    stop=stop_after_delay(3),
                    retry=retry_unless_exception_type(AssertionError),
                )()
        else:
            await _received_project_update_event()


async def _delete_project(client: TestClient, project: dict) -> ClientResponse:
    assert client.app

    url = client.app.router["delete_project"].url_for(project_id=project["uuid"])
    assert str(url) == f"{API_PREFIX}/projects/{project['uuid']}"
    return await client.delete(f"{url}")


@pytest.mark.parametrize(*standard_role_response())
async def test_share_project_user_roles(
    mock_dynamic_scheduler: None,
    client: TestClient,
    logged_user: dict,
    primary_group: dict[str, str],
    standard_groups: list[dict[str, str]],
    all_group: dict[str, str],
    user_role: UserRole,
    expected: ExpectedResponse,
    storage_subsystem_mock,
    mocked_dynamic_services_interface: dict[str, mock.Mock],
    project_db_cleaner,
    request_create_project: Callable[..., Awaitable[ProjectDict]],
    exit_stack: contextlib.AsyncExitStack,
):
    # Use-case: test how different user roles can access shared projects
    # Test with full access rights for all roles
    share_rights = {"read": True, "write": True, "delete": True}

    # create a project with full access rights for the all_group
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
            f"{primary_group['gid']}": {"read": True, "write": True, "delete": True},
            f"{(all_group['gid'])}": share_rights,
        }

        # user 1 can always get to his project
        await assert_get_same_project(client, new_project, expected.ok)

    # get another user logged in now
    await log_client_in(
        client,
        {"role": user_role.name},
        enable_check=user_role != UserRole.ANONYMOUS,
        exit_stack=exit_stack,
    )
    if new_project:
        # user 2 can get the project if they have proper role permissions
        await assert_get_same_project(
            client,
            new_project,
            expected.ok,
        )

        # user 2 can list projects if they have proper role permissions
        list_projects = await _list_projects(client, expected.ok)
        expected_project_count = 1 if user_role != UserRole.ANONYMOUS else 0
        assert len(list_projects) == expected_project_count

        # user 2 can update the project if they have proper role permissions
        project_update = deepcopy(new_project)
        project_update["name"] = "my super name"
        project_update.pop("accessRights")
        await _replace_project(
            client,
            project_update,
            expected.no_content,
        )

        # user 2 can delete projects if they have proper role permissions
        resp = await _delete_project(client, new_project)
        await assert_status(
            resp,
            expected_status_code=expected.no_content,
        )


@pytest.mark.parametrize(*standard_user_role_response())
@pytest.mark.parametrize(
    "share_rights",
    [
        {"read": True, "write": True, "delete": True},
        {"read": True, "write": True, "delete": False},
        {"read": True, "write": False, "delete": False},
        {"read": False, "write": False, "delete": False},
    ],
    ids=["full_access", "no_delete", "read_only", "no_access"],
)
async def test_share_project_access_rights(
    mock_dynamic_scheduler: None,
    client: TestClient,
    logged_user: dict,
    primary_group: dict[str, str],
    standard_groups: list[dict[str, str]],
    all_group: dict[str, str],
    user_role: UserRole,
    expected: ExpectedResponse,
    storage_subsystem_mock,
    mocked_dynamic_services_interface: dict[str, mock.Mock],
    share_rights: dict,
    project_db_cleaner,
    request_create_project: Callable[..., Awaitable[ProjectDict]],
    exit_stack: contextlib.AsyncExitStack,
):
    # Use-case: test how different access rights affect project sharing
    # Test with USER role only but different access rights

    # create a project with specific access rights
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
            f"{primary_group['gid']}": {"read": True, "write": True, "delete": True},
            f"{(all_group['gid'])}": share_rights,
        }

        # user 1 can always get to his project
        await assert_get_same_project(client, new_project, expected.ok)

    # get another user logged in now
    await log_client_in(
        client,
        {"role": user_role.name},
        enable_check=user_role != UserRole.ANONYMOUS,
        exit_stack=exit_stack,
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
    create_socketio_connection_with_handlers: Callable[
        [TestClient], Awaitable[tuple[socketio.AsyncClient, str, _SocketHandlers]]
    ],
    expected: HTTPStatus,
    save_state: bool,
    mocked_dynamic_services_interface: dict[str, mock.Mock],
    mock_service_resources: ServiceResourcesDict,
    mock_orphaned_services: mock.Mock,
    mock_catalog_api: dict[str, mock.Mock],
    osparc_product_name: str,
    osparc_product_api_base_url: str,
    mocked_notifications_plugin: dict[str, mock.Mock],
):
    # POST /v0/projects/{project_id}:open
    # open project
    assert client.app

    # Only create socketio connection for non-anonymous users
    client_id = None
    if expected != status.HTTP_401_UNAUTHORIZED:
        _, client_id, _ = await create_socketio_connection_with_handlers(client)

    url = client.app.router["open_project"].url_for(project_id=user_project["uuid"])
    resp = await client.post(f"{url}", json=client_id)

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
                        product_api_base_url=osparc_product_api_base_url,
                        service_resources=ServiceResourcesDictHelpers.create_jsonable(
                            mock_service_resources
                        ),
                        wallet_info=None,
                        pricing_info=None,
                        hardware_info=None,
                    ),
                )
            )
        mocked_dynamic_services_interface[
            "dynamic_scheduler.api.run_dynamic_service"
        ].assert_has_calls(calls)
    else:
        mocked_notifications_plugin["subscribe"].assert_not_called()


@pytest.fixture
def wallets_clean_db(postgres_db: sa.engine.Engine) -> Iterator[None]:
    with postgres_db.connect() as con:
        yield
        con.execute(wallets.delete())


@pytest.mark.parametrize(
    "user_role,expected,return_value_credits",
    [
        (UserRole.USER, status.HTTP_200_OK, Decimal(0)),
        (UserRole.USER, status.HTTP_402_PAYMENT_REQUIRED, Decimal(-100)),
    ],
)
async def test_open_project__in_debt(
    with_dev_features_enabled: None,
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    create_socketio_connection_with_handlers: Callable[
        [TestClient], Awaitable[tuple[socketio.AsyncClient, str, _SocketHandlers]]
    ],
    expected: HTTPStatus,
    mocked_dynamic_services_interface: dict[str, mock.Mock],
    mock_service_resources: ServiceResourcesDict,
    mock_orphaned_services: mock.Mock,
    mock_catalog_api: dict[str, mock.Mock],
    osparc_product_name: str,
    mocked_notifications_plugin: dict[str, mock.Mock],
    return_value_credits: Decimal,
    mocker: MockerFixture,
    wallets_clean_db: None,
):
    # create a new wallet
    url = client.app.router["create_wallet"].url_for()
    resp = await client.post(
        f"{url}", json={"name": "My first wallet", "description": "Custom description"}
    )
    added_wallet, _ = await assert_status(resp, status.HTTP_201_CREATED)

    mock_get_project_wallet_total_credits = mocker.patch(
        "simcore_service_webserver.projects._wallets_service.credit_transactions.get_project_wallet_total_credits",
        spec=True,
        return_value=WalletTotalCredits(
            wallet_id=added_wallet["walletId"],
            available_osparc_credits=return_value_credits,
        ),
    )

    # Connect project to a wallet
    base_url = client.app.router["connect_wallet_to_project"].url_for(
        project_id=user_project["uuid"], wallet_id=f"{added_wallet['walletId']}"
    )
    resp = await client.put(f"{base_url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert data["walletId"] == added_wallet["walletId"]

    # POST /v0/projects/{project_id}:open
    assert client.app

    _, client_id, _ = await create_socketio_connection_with_handlers(client)

    url = client.app.router["open_project"].url_for(project_id=user_project["uuid"])
    resp = await client.post(f"{url}", json=client_id)
    await assert_status(resp, expected)

    assert mock_get_project_wallet_total_credits.assert_called_once


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
    create_socketio_connection_with_handlers: Callable[
        [TestClient], Awaitable[tuple[socketio.AsyncClient, str, _SocketHandlers]]
    ],
    expected: HTTPStatus,
    save_state: bool,
    mocked_dynamic_services_interface: dict[str, mock.Mock],
    mock_service_resources: ServiceResourcesDict,
    mock_orphaned_services: mock.Mock,
    mock_catalog_api: dict[str, mock.Mock],
    osparc_product_name: str,
    osparc_product_api_base_url: str,
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

    # Only create socketio connection for non-anonymous users
    client_id = None
    if expected != status.HTTP_401_UNAUTHORIZED:
        _, client_id, _ = await create_socketio_connection_with_handlers(client)
    url = client.app.router["open_project"].url_for(project_id=template_project["uuid"])
    resp = await client.post(f"{url}", json=client_id)
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
                        product_api_base_url=osparc_product_api_base_url,
                        wallet_info=None,
                        pricing_info=None,
                        hardware_info=None,
                    ),
                )
            )
        mocked_dynamic_services_interface[
            "dynamic_scheduler.api.run_dynamic_service"
        ].assert_has_calls(calls)
    else:
        mocked_notifications_plugin["subscribe"].assert_not_called()


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.USER, status.HTTP_403_FORBIDDEN),
        (UserRole.TESTER, status.HTTP_403_FORBIDDEN),
    ],
)
async def test_open_template_project_for_edition_with_missing_write_rights(
    client: TestClient,
    logged_user: UserInfoDict,
    create_template_project: Callable[..., Awaitable[ProjectDict]],
    create_socketio_connection_with_handlers: Callable[
        [TestClient], Awaitable[tuple[socketio.AsyncClient, str, _SocketHandlers]]
    ],
    expected: HTTPStatus,
    mocked_dynamic_services_interface: dict[str, mock.Mock],
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

    # Only create socketio connection for non-anonymous users
    client_id = None
    if expected != status.HTTP_401_UNAUTHORIZED:
        _, client_id, _ = await create_socketio_connection_with_handlers(client)
    url = client.app.router["open_project"].url_for(project_id=template_project["uuid"])
    resp = await client.post(f"{url}", json=client_id)
    await assert_status(resp, expected)


@pytest.mark.parametrize(*standard_user_role_response())
async def test_open_project_with_small_amount_of_dynamic_services_starts_them_automatically(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project_with_num_dynamic_services: Callable[[int], Awaitable[ProjectDict]],
    create_socketio_connection_with_handlers: Callable[
        [TestClient], Awaitable[tuple[socketio.AsyncClient, str, _SocketHandlers]]
    ],
    expected: ExpectedResponse,
    mocked_dynamic_services_interface: dict[str, mock.Mock],
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

    # Only create socketio connection for non-anonymous users
    client_id = ""
    if expected.ok:
        _, client_id, _ = await create_socketio_connection_with_handlers(client)
    url = client.app.router["open_project"].url_for(project_id=project["uuid"])
    resp = await client.post(f"{url}", json=client_id)
    await assert_status(resp, expected.ok)
    mocked_notifications_plugin["subscribe"].assert_called_once_with(
        client.app, ProjectID(project["uuid"])
    )
    mocked_notifications_plugin["subscribe"].reset_mock()
    assert mocked_dynamic_services_interface[
        "dynamic_scheduler.api.run_dynamic_service"
    ].call_count == (num_of_dyn_services - num_service_already_running)
    mocked_dynamic_services_interface[
        "dynamic_scheduler.api.run_dynamic_service"
    ].reset_mock()


@pytest.mark.parametrize(*standard_user_role_response())
async def test_open_project_with_disable_service_auto_start_set_overrides_behavior(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project_with_num_dynamic_services: Callable[[int], Awaitable[ProjectDict]],
    create_socketio_connection_with_handlers: Callable[
        [TestClient], Awaitable[tuple[socketio.AsyncClient, str, _SocketHandlers]]
    ],
    expected: ExpectedResponse,
    mocked_dynamic_services_interface: dict[str, mock.Mock],
    mock_catalog_api: dict[str, mock.Mock],
    max_amount_of_auto_started_dyn_services: int,
    mocked_notifications_plugin: dict[str, mock.Mock],
):
    assert client.app
    project = await user_project_with_num_dynamic_services(
        max_amount_of_auto_started_dyn_services
    )
    all_service_uuids = list(project["workbench"])
    for num_service_already_running in range(max_amount_of_auto_started_dyn_services):
        mocked_dynamic_services_interface[
            "dynamic_scheduler.api.list_dynamic_services"
        ].return_value = [
            {"service_uuid": all_service_uuids[service_id]}
            for service_id in range(num_service_already_running)
        ]

        # Only create socketio connection for non-anonymous users
        client_id = ""
        if expected.ok:
            sio, client_id, *_ = await create_socketio_connection_with_handlers(client)
        url = (
            client.app.router["open_project"]
            .url_for(project_id=project["uuid"])
            .with_query(disable_service_auto_start=f"{True}")
        )

        resp = await client.post(f"{url}", json=client_id)
        await assert_status(resp, expected.ok)
        if expected.ok:
            await sio.disconnect()
        mocked_notifications_plugin["subscribe"].assert_called_once_with(
            client.app, ProjectID(project["uuid"])
        )
        mocked_notifications_plugin["subscribe"].reset_mock()
        mocked_dynamic_services_interface[
            "dynamic_scheduler.api.run_dynamic_service"
        ].assert_not_called()


@pytest.mark.parametrize(*standard_user_role_response())
async def test_open_project_with_large_amount_of_dynamic_services_does_not_start_them_automatically(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project_with_num_dynamic_services: Callable[[int], Awaitable[ProjectDict]],
    create_socketio_connection_with_handlers: Callable[
        [TestClient], Awaitable[tuple[socketio.AsyncClient, str, _SocketHandlers]]
    ],
    expected: ExpectedResponse,
    mocked_dynamic_services_interface: dict[str, mock.Mock],
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

    # Only create socketio connection for non-anonymous users
    client_id = ""
    if expected.ok:
        _, client_id, _ = await create_socketio_connection_with_handlers(client)
    url = client.app.router["open_project"].url_for(project_id=project["uuid"])
    resp = await client.post(f"{url}", json=client_id)
    await assert_status(resp, expected.ok)
    mocked_notifications_plugin["subscribe"].assert_called_once_with(
        client.app, ProjectID(project["uuid"])
    )
    mocked_notifications_plugin["subscribe"].reset_mock()
    mocked_dynamic_services_interface[
        "dynamic_scheduler.api.run_dynamic_service"
    ].assert_not_called()


@pytest.mark.parametrize(*standard_user_role_response())
async def test_open_project_with_large_amount_of_dynamic_services_starts_them_if_setting_disabled(
    mock_get_total_project_dynamic_nodes_creation_interval: None,
    disable_max_number_of_running_dynamic_nodes: dict[str, str],
    client: TestClient,
    logged_user: UserInfoDict,
    user_project_with_num_dynamic_services: Callable[[int], Awaitable[ProjectDict]],
    create_socketio_connection_with_handlers: Callable[
        [TestClient], Awaitable[tuple[socketio.AsyncClient, str, _SocketHandlers]]
    ],
    expected: ExpectedResponse,
    mocked_dynamic_services_interface: dict[str, mock.Mock],
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

    # Only create socketio connection for non-anonymous users
    client_id = ""
    if expected.ok:
        _, client_id, _ = await create_socketio_connection_with_handlers(client)
    url = client.app.router["open_project"].url_for(project_id=project["uuid"])
    resp = await client.post(f"{url}", json=client_id)
    await assert_status(resp, expected.ok)
    mocked_notifications_plugin["subscribe"].assert_called_once_with(
        client.app, ProjectID(project["uuid"])
    )
    mocked_notifications_plugin["subscribe"].reset_mock()
    mocked_dynamic_services_interface[
        "dynamic_scheduler.api.run_dynamic_service"
    ].assert_called()


@pytest.mark.parametrize(*standard_user_role_response())
async def test_open_project_with_deprecated_services_ok_but_does_not_start_dynamic_services(
    client: TestClient,
    logged_user,
    user_project,
    create_socketio_connection_with_handlers: Callable[
        [TestClient], Awaitable[tuple[socketio.AsyncClient, str, _SocketHandlers]]
    ],
    expected: ExpectedResponse,
    mocked_dynamic_services_interface: dict[str, mock.Mock],
    mock_service_resources: ServiceResourcesDict,
    mock_orphaned_services,
    mock_catalog_api: dict[str, mock.Mock],
    mocked_notifications_plugin: dict[str, mock.Mock],
):
    mock_catalog_api["get_service"].return_value["deprecated"] = (
        datetime.now(UTC) - timedelta(days=1)
    ).isoformat()
    # Only create socketio connection for non-anonymous users
    client_id = ""
    if expected.ok:
        _, client_id, _ = await create_socketio_connection_with_handlers(client)
    url = client.app.router["open_project"].url_for(project_id=user_project["uuid"])
    resp = await client.post(url, json=client_id)
    await assert_status(resp, expected.ok)
    mocked_notifications_plugin["subscribe"].assert_called_once_with(
        client.app, ProjectID(user_project["uuid"])
    )
    mocked_dynamic_services_interface[
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


@pytest.mark.parametrize(*standard_user_role_response())
async def test_open_project_more_than_limitation_of_max_studies_open_per_user(
    one_max_open_studies_per_user: None,
    client: TestClient,
    logged_user,
    create_socketio_connection_with_handlers: Callable[
        [TestClient], Awaitable[tuple[socketio.AsyncClient, str, _SocketHandlers]]
    ],
    user_project: ProjectDict,
    shared_project: ProjectDict,
    expected: ExpectedResponse,
    mocked_dynamic_services_interface: dict[str, mock.Mock],
    mock_catalog_api: dict[str, mock.Mock],
    user_role: UserRole,
    mocked_notifications_plugin: dict[str, mock.Mock],
):
    # Only create socketio connection for non-anonymous users
    client_id_1 = ""
    if user_role != UserRole.ANONYMOUS:
        _, client_id_1, _ = await create_socketio_connection_with_handlers(client)
    await _open_project(
        client,
        client_id_1,
        user_project,
        HTTPStatus(expected.ok) if user_role != UserRole.GUEST else HTTPStatus.OK,
    )

    # Only create socketio connection for non-anonymous users
    client_id_2 = ""
    if user_role != UserRole.ANONYMOUS:
        _, client_id_2, _ = await create_socketio_connection_with_handlers(client)
    await _open_project(
        client,
        client_id_2,
        shared_project,
        (
            HTTPStatus(expected.conflict)
            if user_role != UserRole.GUEST
            else HTTPStatus.CONFLICT
        ),
    )


@pytest.mark.parametrize(*standard_role_response())
async def test_close_project(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    client_session_id_factory: Callable[[], str],
    expected,
    mocked_dynamic_services_interface: dict[str, mock.Mock],
    mock_catalog_api: dict[str, mock.Mock],
    fake_services: Callable[..., Awaitable[list[DynamicServiceGet]]],
    mock_dynamic_scheduler_rabbitmq: None,
    mocked_notifications_plugin: dict[str, mock.Mock],
):
    # POST /v0/projects/{project_id}:close
    fake_dynamic_services = await fake_services(number_services=5)
    assert len(fake_dynamic_services) == 5
    mocked_dynamic_services_interface[
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
        mocked_dynamic_services_interface[
            "dynamic_scheduler.api.list_dynamic_services"
        ].assert_any_call(
            client.app, user_id=user_id, project_id=ProjectID(user_project["uuid"])
        )
        mocked_dynamic_services_interface[
            "dynamic_scheduler.api.list_dynamic_services"
        ].reset_mock()
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
                project_id=ProjectID(user_project["uuid"]),
            ),
        ]
        mocked_dynamic_services_interface[
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
        mocked_dynamic_services_interface[
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
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    expected: int,
    create_socketio_connection: Callable[
        [str | None, TestClient | None], Awaitable[tuple[socketio.AsyncClient, str]]
    ],
    mocked_dynamic_services_interface: dict[str, mock.Mock],
    mock_catalog_api: dict[str, mock.Mock],
    mocked_notifications_plugin: dict[str, mock.Mock],
):
    # login with socket using client session id
    client_id1 = ""
    try:
        sio, client_id1 = await create_socketio_connection(None, client)
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
        assert ProjectStateOutputSchema(**data.pop("state")).share_state.locked
        data.pop("folderId", None)

        user_project_last_change_date = user_project.pop("lastChangeDate")
        data_last_change_date = data.pop("lastChangeDate")
        assert user_project_last_change_date < data_last_change_date

        assert data == {k: user_project[k] for k in data}
    else:
        mocked_notifications_plugin["subscribe"].assert_not_called()

    # login with socket using client session id2
    client_id2 = ""
    try:
        sio, client_id2 = await create_socketio_connection(None, client)
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
    mock_dynamic_scheduler: None,
    client: TestClient,
    logged_user: UserInfoDict,
    user_project,
    expected_response_on_create,
    expected_response_on_get,
    expected_response_on_delete,
    mocked_dynamic_services_interface: dict[str, mock.Mock],
    storage_subsystem_mock,
    mock_catalog_api: dict[str, mock.Mock],
    mocker,
    faker: Faker,
    create_dynamic_service_mock: Callable[..., Awaitable[DynamicServiceGet]],
):
    mock_storage_api_delete_data_folders_of_project_node = mocker.patch(
        "simcore_service_webserver.projects._projects_service.storage_service.delete_data_folders_of_project_node",
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
        mocked_dynamic_services_interface[
            "dynamic_scheduler.api.run_dynamic_service"
        ].assert_called_once()
        assert "node_id" in data
        dynamic_node_id = data["node_id"]
    else:
        mocked_dynamic_services_interface[
            "dynamic_scheduler.api.run_dynamic_service"
        ].assert_not_called()

    # create a new NOT dynamic node...
    mocked_dynamic_services_interface[
        "dynamic_scheduler.api.run_dynamic_service"
    ].reset_mock()
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
        mocked_dynamic_services_interface[
            "dynamic_scheduler.api.run_dynamic_service"
        ].assert_not_called()
        assert "node_id" in data
        computational_node_id = data["node_id"]
    else:
        mocked_dynamic_services_interface[
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
    assert node_sample
    assert isinstance(node_sample, dict)
    mocked_dynamic_services_interface[
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
    mocked_dynamic_services_interface[
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
        mocked_dynamic_services_interface[
            "dynamic_scheduler.api.stop_dynamic_service"
        ].assert_called_once()
        mock_storage_api_delete_data_folders_of_project_node.assert_called_once()
    else:
        mocked_dynamic_services_interface[
            "dynamic_scheduler.api.stop_dynamic_service"
        ].assert_not_called()
        mock_storage_api_delete_data_folders_of_project_node.assert_not_called()

    # delete the NOT dynamic node
    mocked_dynamic_services_interface[
        "dynamic_scheduler.api.stop_dynamic_service"
    ].reset_mock()
    mock_storage_api_delete_data_folders_of_project_node.reset_mock()
    url = client.app.router["delete_node"].url_for(
        project_id=user_project["uuid"], node_id=computational_node_id
    )
    resp = await client.delete(f"{url}")
    data, errors = await assert_status(resp, expected_response_on_delete)
    if resp.status == status.HTTP_204_NO_CONTENT:
        mocked_dynamic_services_interface[
            "dynamic_scheduler.api.stop_dynamic_service"
        ].assert_not_called()
        mock_storage_api_delete_data_folders_of_project_node.assert_called_once()
    else:
        mocked_dynamic_services_interface[
            "dynamic_scheduler.api.stop_dynamic_service"
        ].assert_not_called()
        mock_storage_api_delete_data_folders_of_project_node.assert_not_called()


@pytest.fixture
async def client_on_running_server_factory(
    client: TestClient,
) -> AsyncIterator[Callable[[], TestClient]]:
    # Creates clients connected to the same server as the reference client
    #
    # Implemented as aihttp_client but creates a client using a running server,
    #  i.e. avoid client.start_server

    assert isinstance(client.server, TestServer)

    clients = []

    def go() -> TestClient:
        cli = TestClient(client.server, loop=asyncio.get_event_loop())
        assert client.server.started
        # AVOIDS client.start_server
        clients.append(cli)
        return cli

    yield go

    async def close_client_but_not_server(cli: TestClient) -> None:
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

    await finalize()


@pytest.fixture
def clean_redis_table(redis_client) -> None:
    """this just ensures the redis table is cleaned up between test runs"""


@pytest.mark.parametrize(*standard_user_role_response())
async def test_open_shared_project_multiple_users(
    max_number_of_user_sessions: int,
    with_enabled_rtc_collaboration: None,
    client: TestClient,
    client_on_running_server_factory: Callable[[], TestClient],
    logged_user: dict,
    shared_project: dict,
    expected: ExpectedResponse,
    exit_stack: contextlib.AsyncExitStack,
    create_socketio_connection_with_handlers: Callable[
        [TestClient], Awaitable[tuple[socketio.AsyncClient, str, _SocketHandlers]]
    ],
    mocked_dynamic_services_interface: dict[str, mock.Mock],
    mock_catalog_api: dict[str, mock.Mock],
):
    base_client = client
    (
        sio_base,
        base_client_tab_id,
        sio_base_handlers,
    ) = await create_socketio_connection_with_handlers(base_client)

    # current state is closed and unlocked
    closed_project_state = ProjectStateOutputSchema(
        share_state=ProjectShareStateOutputSchema(
            locked=False, status=ProjectStatus.CLOSED, current_user_groupids=[]
        ),
        state=ProjectRunningState(value=RunningState.NOT_STARTED),
    )
    await _state_project(base_client, shared_project, expected.ok, closed_project_state)

    # now user 1 opens the shared project
    await _open_project(base_client, base_client_tab_id, shared_project, expected.ok)
    opened_project_state = closed_project_state.model_copy(
        update={
            "share_state": ProjectShareStateOutputSchema(
                locked=False,
                status=ProjectStatus.OPENED,
                current_user_groupids=[logged_user["primary_gid"]],
            ),
        }
    )
    await _assert_project_state_updated(
        sio_base_handlers[SOCKET_IO_PROJECT_UPDATED_EVENT],
        shared_project,
        [opened_project_state] * 2,
    )
    await _state_project(base_client, shared_project, expected.ok, opened_project_state)

    # now we create more users and open the same project until we reach the maximum number of user sessions
    other_users: list[
        tuple[UserInfoDict, TestClient, str, socketio.AsyncClient, _SocketHandlers]
    ] = []
    for user_session in range(1, max_number_of_user_sessions):
        client_i = client_on_running_server_factory()

        # user i logs in
        user_i = await exit_stack.enter_async_context(
            LoggedUser(client_i, {"role": logged_user["role"]})
        )

        (
            sio_i,
            client_i_tab_id,
            sio_i_handlers,
        ) = await create_socketio_connection_with_handlers(client_i)
        assert sio_i

        # user i opens the shared project
        await _open_project(client_i, client_i_tab_id, shared_project, expected.ok)
        opened_project_state = opened_project_state.model_copy(
            update={
                "share_state": ProjectShareStateOutputSchema(
                    locked=(not user_session < max_number_of_user_sessions - 1),
                    status=ProjectStatus.OPENED,
                    current_user_groupids=[
                        *opened_project_state.share_state.current_user_groupids,
                        TypeAdapter(GroupID).validate_python(user_i["primary_gid"]),
                    ],
                ),
            }
        )
        await _assert_project_state_updated(
            sio_i_handlers[SOCKET_IO_PROJECT_UPDATED_EVENT],
            shared_project,
            [opened_project_state]
            * 1,  # NOTE: only one call per user since they are part of the everyone group
        )
        for _user_j, client_j, _, _sio_j, sio_j_handlers in other_users:
            # check already opened  by other users which should also notify
            await _assert_project_state_updated(
                sio_j_handlers[SOCKET_IO_PROJECT_UPDATED_EVENT],
                shared_project,
                [opened_project_state],
            )
            await _state_project(
                client_j, shared_project, expected.ok, opened_project_state
            )

        await _assert_project_state_updated(
            sio_base_handlers[SOCKET_IO_PROJECT_UPDATED_EVENT],
            shared_project,
            [opened_project_state]
            * 2,  # NOTE: 2 calls since base user is part of the primary group and the all group
        )
        await _state_project(
            client_i, shared_project, expected.ok, opened_project_state
        )
        await _state_project(
            base_client, shared_project, expected.ok, opened_project_state
        )
        other_users.append((user_i, client_i, client_i_tab_id, sio_i, sio_i_handlers))

    # create an additional user, opening the project again shall raise
    client_n = client_on_running_server_factory()

    user_n = await exit_stack.enter_async_context(
        LoggedUser(client_n, {"role": logged_user["role"]})
    )
    assert user_n

    (
        sio_n,
        client_n_tab_id,
        sio_n_handlers,
    ) = await create_socketio_connection_with_handlers(client_n)
    assert sio_n
    assert sio_n_handlers

    # user i opens the shared project --> no events since it's blocked
    await _open_project(client_n, client_n_tab_id, shared_project, expected.conflict)
    await _assert_project_state_updated(
        sio_n_handlers[SOCKET_IO_PROJECT_UPDATED_EVENT], shared_project, []
    )

    # close project from a random user shall trigger an event for all the other users
    await _close_project(
        base_client, base_client_tab_id, shared_project, expected.no_content
    )
    opened_project_state = opened_project_state.model_copy(
        update={
            "share_state": ProjectShareStateOutputSchema(
                locked=False,
                status=ProjectStatus.OPENED,
                current_user_groupids=[
                    gid
                    for gid in opened_project_state.share_state.current_user_groupids
                    if gid
                    != TypeAdapter(GroupID).validate_python(logged_user["primary_gid"])
                ],
            ),
        }
    )
    await _assert_project_state_updated(
        sio_base_handlers[SOCKET_IO_PROJECT_UPDATED_EVENT],
        shared_project,
        [opened_project_state] * 2,
    )
    # check all the other users
    for _user_i, client_i, _, _sio_i, sio_i_handlers in other_users:
        await _assert_project_state_updated(
            sio_i_handlers[SOCKET_IO_PROJECT_UPDATED_EVENT],
            shared_project,
            [opened_project_state],
        )
        await _state_project(
            client_i, shared_project, expected.ok, opened_project_state
        )


@pytest.mark.parametrize(*standard_user_role_response())
async def test_open_shared_project_2_users_locked_remove_once_rtc_collaboration_is_defaulted(
    client: TestClient,
    client_on_running_server_factory: Callable[[], TestClient],
    logged_user: dict,
    shared_project: dict,
    user_role: UserRole,
    expected: ExpectedResponse,
    mocked_dynamic_services_interface: dict[str, mock.Mock],
    mock_orphaned_services,
    mock_catalog_api: dict[str, mock.Mock],
    clean_redis_table: None,
    mock_dynamic_scheduler_rabbitmq: None,
    mocked_notifications_plugin: dict[str, mock.Mock],
    exit_stack: contextlib.AsyncExitStack,
    create_socketio_connection_with_handlers: Callable[
        [TestClient], Awaitable[tuple[socketio.AsyncClient, str, _SocketHandlers]]
    ],
):
    # Use-case: user 1 opens a shared project, user 2 tries to open it as well

    client_1 = client
    client_2 = client_on_running_server_factory()

    # 1. user 1 opens project
    sio1, client_id1, sio1_handlers = await create_socketio_connection_with_handlers(
        client_1
    )
    # expected is that the project is closed and unlocked
    expected_project_state_client_1 = ProjectStateOutputSchema(
        share_state=ProjectShareStateOutputSchema(
            locked=False, status=ProjectStatus.CLOSED, current_user_groupids=[]
        ),
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
    expected_project_state_client_1 = expected_project_state_client_1.model_copy(
        update={
            "share_state": ProjectShareStateOutputSchema(
                locked=True,
                status=ProjectStatus.OPENED,
                current_user_groupids=[
                    logged_user["primary_gid"]
                ],  # this should be the group of that user
            ),
        }
    )

    # NOTE: there are 2 calls since we are part of the primary group and the all group
    await _assert_project_state_updated(
        sio1_handlers[SOCKET_IO_PROJECT_UPDATED_EVENT],
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
        client_2,
        {"role": user_role.name},
        enable_check=user_role != UserRole.ANONYMOUS,
        exit_stack=exit_stack,
    )
    sio2, client_id2, sio2_handlers = await create_socketio_connection_with_handlers(
        client_2
    )
    await _open_project(
        client_2,
        client_id2,
        shared_project,
        expected.locked if user_role != UserRole.GUEST else status.HTTP_423_LOCKED,
    )
    expected_project_state_client_2 = expected_project_state_client_1.model_copy(
        update={
            "share_state": ProjectShareStateOutputSchema(
                locked=expected_project_state_client_1.share_state.locked,
                status=ProjectStatus.OPENED,
                current_user_groupids=expected_project_state_client_1.share_state.current_user_groupids,
            ),
        }
    )

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
        expected_project_state_client_1 = ProjectStateOutputSchema(
            share_state=ProjectShareStateOutputSchema(
                locked=False, status=ProjectStatus.CLOSED, current_user_groupids=[]
            ),
            state=ProjectRunningState(value=RunningState.NOT_STARTED),
        )

    # we should receive an event that the project lock state changed
    # NOTE: user 1 is part of the primary group owning the project, and the all group
    # there will be an event when the project is CLOSING, then another once the services are removed and the project is CLOSED
    # user 2 is only part of the all group, therefore only receives 1 event

    await _assert_project_state_updated(
        sio1_handlers[SOCKET_IO_PROJECT_UPDATED_EVENT],
        shared_project,
        [
            expected_project_state_client_1.model_copy(
                update={
                    "share_state": ProjectShareStateOutputSchema(
                        locked=True,
                        status=ProjectStatus.CLOSING,
                        current_user_groupids=[logged_user["primary_gid"]],
                    )
                }
            )
        ]
        * (
            0
            if any(user_role == role for role in [UserRole.ANONYMOUS, UserRole.GUEST])
            else 2
        )
        + [expected_project_state_client_1]
        * (
            0
            if any(user_role == role for role in [UserRole.ANONYMOUS, UserRole.GUEST])
            else 2
        ),
    )
    await _assert_project_state_updated(
        sio2_handlers[SOCKET_IO_PROJECT_UPDATED_EVENT],
        shared_project,
        [
            expected_project_state_client_1.model_copy(
                update={
                    "share_state": ProjectShareStateOutputSchema(
                        locked=True,
                        status=ProjectStatus.CLOSING,
                        current_user_groupids=[logged_user["primary_gid"]],
                    )
                }
            )
        ]
        * (
            0
            if any(user_role == role for role in [UserRole.ANONYMOUS, UserRole.GUEST])
            else 1
        )
        + [expected_project_state_client_1]
        * (
            0
            if any(user_role == role for role in [UserRole.ANONYMOUS, UserRole.GUEST])
            else 1
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
        expected_project_state_client_2 = expected_project_state_client_1.model_copy(
            update={
                "share_state": ProjectShareStateOutputSchema(
                    locked=True,
                    status=ProjectStatus.OPENED,
                    current_user_groupids=[int(user_2["primary_gid"])],
                ),
            }
        )
        expected_project_state_client_1 = expected_project_state_client_1.model_copy(
            update={
                "share_state": ProjectShareStateOutputSchema(
                    locked=True,
                    status=ProjectStatus.OPENED,
                    current_user_groupids=[int(user_2["primary_gid"])],
                ),
            }
        )

    # NOTE: there are 3 calls since we are part of the primary group and the all group
    await _assert_project_state_updated(
        sio1_handlers[SOCKET_IO_PROJECT_UPDATED_EVENT],
        shared_project,
        [expected_project_state_client_1]
        * (
            0
            if any(user_role == role for role in [UserRole.ANONYMOUS, UserRole.GUEST])
            else 2
        ),
    )
    await _assert_project_state_updated(
        sio2_handlers[SOCKET_IO_PROJECT_UPDATED_EVENT],
        shared_project,
        [expected_project_state_client_1]
        * (
            0
            if any(user_role == role for role in [UserRole.ANONYMOUS, UserRole.GUEST])
            else 1
        ),
    )
    await _state_project(
        client_1,
        shared_project,
        expected.ok if user_role != UserRole.GUEST else status.HTTP_200_OK,
        expected_project_state_client_1,
    )


@pytest.mark.parametrize(*standard_user_role_response())
async def test_open_shared_project_at_same_time(
    client: TestClient,
    client_on_running_server_factory: Callable[[], TestClient],
    logged_user: dict,
    shared_project: ProjectDict,
    user_role: UserRole,
    expected: ExpectedResponse,
    mocked_dynamic_services_interface: dict[str, mock.Mock],
    mock_orphaned_services,
    mock_catalog_api: dict[str, mock.Mock],
    clean_redis_table,
    mock_dynamic_scheduler_rabbitmq: None,
    mocked_notifications_plugin: dict[str, mock.Mock],
    exit_stack: contextlib.AsyncExitStack,
    create_socketio_connection_with_handlers: Callable[
        [TestClient], Awaitable[tuple[socketio.AsyncClient, str, _SocketHandlers]]
    ],
):
    NUMBER_OF_ADDITIONAL_CLIENTS = 10
    # log client 1
    client_1 = client
    sio_1, client_id1, _ = await create_socketio_connection_with_handlers(client_1)
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
            exit_stack=exit_stack,
        )
        sio, client_id, _ = await create_socketio_connection_with_handlers(new_client)
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
    assert isinstance(results, list)
    # one should be opened, the other locked
    if user_role != UserRole.ANONYMOUS:
        num_assertions = 0
        for data, error in results:
            assert data or error
            if error:
                num_assertions += 1
            elif data:
                project_status = ProjectStateOutputSchema(**data.pop("state"))
                data.pop("folderId")
                assert not DeepDiff(
                    data,
                    {k: shared_project[k] for k in data},
                    exclude_paths=["root['lastChangeDate']"],
                )
                assert project_status.share_state.locked
                assert project_status.share_state.current_user_groupids
                assert len(project_status.share_state.current_user_groupids) == 1
                assert project_status.share_state.current_user_groupids[0] in [
                    c["user"]["primary_gid"] for c in clients
                ]

        assert num_assertions == NUMBER_OF_ADDITIONAL_CLIENTS


@pytest.mark.parametrize(*standard_user_role_response())
async def test_opened_project_can_still_be_opened_after_refreshing_tab(
    client: TestClient,
    logged_user: dict[str, Any],
    user_project: dict[str, Any],
    user_role: UserRole,
    expected: ExpectedResponse,
    mocked_dynamic_services_interface: dict[str, mock.MagicMock],
    mock_orphaned_services,
    mock_catalog_api: dict[str, mock.Mock],
    clean_redis_table,
    mocked_notifications_plugin: dict[str, mock.Mock],
    create_socketio_connection: Callable[
        [str | None, TestClient | None], Awaitable[tuple[socketio.AsyncClient, str]]
    ],
):
    """Simulating a refresh goes as follows:
    The user opens a project, then hit the F5 refresh page.
    The browser disconnects the websocket, reconnects but the
    client_session_id remains the same
    """

    sio, client_session_id = await create_socketio_connection(None, client)
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
    sio2, received_client_session_id = await create_socketio_connection(
        client_session_id, client
    )
    assert sio2
    assert received_client_session_id == client_session_id
    # re-open the project
    resp = await client.post(f"{url}", json=client_session_id)
    await assert_status(
        resp, expected.ok if user_role != UserRole.GUEST else status.HTTP_200_OK
    )
