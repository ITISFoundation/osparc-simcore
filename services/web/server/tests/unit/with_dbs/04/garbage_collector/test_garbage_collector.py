import asyncio
from collections.abc import Awaitable, Callable
from typing import Any
from unittest import mock

import pytest
import socketio
from aiohttp.test_utils import TestClient
from aioresponses import aioresponses
from common_library.users_enums import UserRole
from fastapi.encoders import jsonable_encoder
from models_library.api_schemas_directorv2.dynamic_services import DynamicServiceGet
from models_library.api_schemas_dynamic_scheduler.dynamic_services import (
    DynamicServiceStop,
)
from pytest_mock import MockerFixture
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.webserver_parametrizations import MockedStorageSubsystem
from pytest_simcore.helpers.webserver_users import UserInfoDict
from servicelib.aiohttp import status
from servicelib.common_headers import UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE
from simcore_service_webserver.garbage_collector import _core as gc_core
from simcore_service_webserver.socketio.messages import SOCKET_IO_PROJECT_UPDATED_EVENT
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_delay,
    wait_fixed,
)

_TENACITY_ASSERT_RETRY = {
    "reraise": True,
    "retry": retry_if_exception_type(AssertionError),
    "wait": wait_fixed(0.5),
    "stop": stop_after_delay(30),
}


@pytest.mark.parametrize(
    "user_role, expected_save_state",
    [
        (UserRole.GUEST, False),
        (UserRole.USER, True),
        (UserRole.TESTER, True),
    ],
)
async def test_interactive_services_removed_after_logout(
    fast_service_deletion_delay: int,
    client: TestClient,
    logged_user: dict[str, Any],
    empty_user_project: dict[str, Any],
    mocked_dynamic_services_interface: dict[str, mock.MagicMock],
    create_dynamic_service_mock: Callable[..., Awaitable[DynamicServiceGet]],
    client_session_id_factory: Callable[[], str],
    create_socketio_connection: Callable,
    storage_subsystem_mock: MockedStorageSubsystem,  # when guest user logs out garbage is collected
    director_v2_service_mock: aioresponses,
    expected_save_state: bool,
    open_project: Callable,
    mocked_notifications_plugin: dict[str, mock.Mock],
):
    assert client.app
    user_id = logged_user["id"]
    service = await create_dynamic_service_mock(
        user_id=user_id, project_id=empty_user_project["uuid"]
    )
    # create websocket
    client_session_id1 = client_session_id_factory()
    sio = await create_socketio_connection(client_session_id1)
    assert sio
    # open project in client 1
    await open_project(client, empty_user_project["uuid"], client_session_id1)
    # logout
    logout_url = client.app.router["auth_logout"].url_for()
    r = await client.post(
        f"{logout_url}", json={"client_session_id": client_session_id1}
    )
    assert r.url.path == logout_url.path
    await assert_status(r, status.HTTP_200_OK)

    # check result perfomed by background task
    await asyncio.sleep(fast_service_deletion_delay + 1)
    await gc_core.collect_garbage(client.app)

    # assert dynamic service is removed *this is done in a fire/forget way so give a bit of leeway
    async for attempt in AsyncRetrying(**_TENACITY_ASSERT_RETRY):
        with attempt:
            print(
                f"--> Waiting for stop_dynamic_service with: {service.node_uuid}, {expected_save_state=}",
            )
            mocked_dynamic_services_interface[
                "dynamic_scheduler.api.stop_dynamic_service"
            ].assert_awaited_with(
                app=client.app,
                dynamic_service_stop=DynamicServiceStop(
                    user_id=user_id,
                    project_id=service.project_id,
                    node_id=service.node_uuid,
                    simcore_user_agent=UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE,
                    save_state=expected_save_state,
                ),
                progress=mock.ANY,
            )


@pytest.mark.parametrize(
    "user_role, expected_save_state",
    [
        (UserRole.GUEST, False),
        (UserRole.USER, True),
        (UserRole.TESTER, True),
    ],
)
async def test_interactive_services_remain_after_websocket_reconnection_from_2_tabs(
    fast_service_deletion_delay: int,
    director_v2_service_mock: aioresponses,
    client: TestClient,
    logged_user: UserInfoDict,
    empty_user_project,
    mocked_dynamic_services_interface,
    create_dynamic_service_mock: Callable[..., Awaitable[DynamicServiceGet]],
    create_socketio_connection: Callable,
    client_session_id_factory: Callable[[], str],
    storage_subsystem_mock,  # when guest user logs out garbage is collected
    expected_save_state: bool,
    mocker: MockerFixture,
    open_project: Callable,
    mocked_notifications_plugin: dict[str, mock.Mock],
):
    assert client.app
    user_id = logged_user["id"]
    service = await create_dynamic_service_mock(
        user_id=user_id, project_id=empty_user_project["uuid"]
    )
    # create first websocket
    client_session_id1 = client_session_id_factory()
    sio = await create_socketio_connection(client_session_id1)
    # open project in client 1
    await open_project(client, empty_user_project["uuid"], client_session_id1)

    # create second websocket
    client_session_id2 = client_session_id_factory()
    sio2 = await create_socketio_connection(client_session_id2)
    assert sio.sid != sio2.sid
    socket_project_state_update_mock_callable = mocker.Mock()
    sio2.on(
        SOCKET_IO_PROJECT_UPDATED_EVENT,
        handler=socket_project_state_update_mock_callable,
    )
    # disconnect first websocket
    # NOTE: since the service deletion delay is set to 1 second for the test, we should not sleep as long here, or the user will be deleted
    # We have no mock-up for the heatbeat...
    await sio.disconnect()
    assert not sio.sid
    async for attempt in AsyncRetrying(
        **(_TENACITY_ASSERT_RETRY | {"wait": wait_fixed(0.1)})
    ):
        with attempt:
            socket_project_state_update_mock_callable.assert_called_with(
                jsonable_encoder(
                    {
                        "project_uuid": empty_user_project["uuid"],
                        "data": {
                            "shareState": {
                                "locked": False,
                                "currentUserGroupids": [logged_user["primary_gid"]],
                                "status": "OPENED",
                            },
                            "state": {"value": "NOT_STARTED"},
                        },
                    }
                )
            )
    # open project in second client
    await open_project(client, empty_user_project["uuid"], client_session_id2)
    # ensure sufficient time is wasted here
    await asyncio.sleep(fast_service_deletion_delay + 1)
    await gc_core.collect_garbage(client.app)

    # assert dynamic service is still around
    mocked_dynamic_services_interface[
        "dynamic_scheduler.api.stop_dynamic_service"
    ].assert_not_called()
    # disconnect second websocket
    await sio2.disconnect()
    assert not sio2.sid
    # assert dynamic service is still around for now
    mocked_dynamic_services_interface[
        "dynamic_scheduler.api.stop_dynamic_service"
    ].assert_not_called()
    # reconnect websocket
    sio2 = await create_socketio_connection(client_session_id2)
    # it should still be there even after waiting for auto deletion from garbage collector
    await asyncio.sleep(fast_service_deletion_delay + 1)
    await gc_core.collect_garbage(client.app)

    mocked_dynamic_services_interface[
        "dynamic_scheduler.api.stop_dynamic_service"
    ].assert_not_called()
    # now really disconnect
    await sio2.disconnect()
    await sio2.wait()
    assert not sio2.sid
    # run the garbage collector
    # event after waiting some time
    await asyncio.sleep(fast_service_deletion_delay + 1)
    await gc_core.collect_garbage(client.app)

    await asyncio.sleep(0)
    # assert dynamic service is gone
    calls = [
        mock.call(
            app=client.app,
            dynamic_service_stop=DynamicServiceStop(
                user_id=user_id,
                project_id=service.project_id,
                simcore_user_agent=UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE,
                save_state=expected_save_state,
                node_id=service.node_uuid,
            ),
            progress=mock.ANY,
        )
    ]
    mocked_dynamic_services_interface[
        "dynamic_scheduler.api.stop_dynamic_service"
    ].assert_has_calls(calls)


@pytest.mark.parametrize(
    "user_role, expected_save_state",
    [
        (UserRole.GUEST, False),
        (UserRole.USER, True),
        (UserRole.TESTER, True),
    ],
)
async def test_interactive_services_removed_per_project(
    fast_service_deletion_delay: int,
    director_v2_service_mock: aioresponses,
    client,
    logged_user,
    empty_user_project,
    empty_user_project2,
    mocked_dynamic_services_interface,
    create_dynamic_service_mock: Callable[..., Awaitable[DynamicServiceGet]],
    mocked_notification_system,
    create_socketio_connection: Callable,
    client_session_id_factory: Callable[[], str],
    storage_subsystem_mock,  # when guest user logs out garbage is collected
    expected_save_state: bool,
    open_project: Callable,
    mocked_notifications_plugin: dict[str, mock.Mock],
):
    user_id = logged_user["id"]
    # create server with delay set to DELAY
    service1 = await create_dynamic_service_mock(
        user_id=user_id, project_id=empty_user_project["uuid"]
    )
    service2 = await create_dynamic_service_mock(
        user_id=user_id, project_id=empty_user_project2["uuid"]
    )
    service3 = await create_dynamic_service_mock(
        user_id=user_id, project_id=empty_user_project2["uuid"]
    )
    # create websocket1 from tab1
    client_session_id1 = client_session_id_factory()
    sio1 = await create_socketio_connection(client_session_id1)
    await open_project(client, empty_user_project["uuid"], client_session_id1)
    # create websocket2 from tab2
    client_session_id2 = client_session_id_factory()
    sio2 = await create_socketio_connection(client_session_id2)
    await open_project(client, empty_user_project2["uuid"], client_session_id2)
    # disconnect websocket1
    await sio1.disconnect()
    assert not sio1.sid
    # assert dynamic service is still around
    mocked_dynamic_services_interface[
        "dynamic_scheduler.api.stop_dynamic_service"
    ].assert_not_called()
    # wait the defined delay
    await asyncio.sleep(fast_service_deletion_delay + 1)
    await gc_core.collect_garbage(client.app)
    # assert dynamic service 1 is removed
    calls = [
        mock.call(
            app=client.app,
            dynamic_service_stop=DynamicServiceStop(
                user_id=user_id,
                project_id=service1.project_id,
                node_id=service1.node_uuid,
                simcore_user_agent=UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE,
                save_state=expected_save_state,
            ),
            progress=mock.ANY,
        )
    ]
    mocked_dynamic_services_interface[
        "dynamic_scheduler.api.stop_dynamic_service"
    ].assert_has_calls(calls)
    mocked_dynamic_services_interface[
        "dynamic_scheduler.api.stop_dynamic_service"
    ].reset_mock()

    # disconnect websocket2
    await sio2.disconnect()
    assert not sio2.sid
    # assert dynamic services are still around
    mocked_dynamic_services_interface[
        "dynamic_scheduler.api.stop_dynamic_service"
    ].assert_not_called()
    # wait the defined delay
    await asyncio.sleep(fast_service_deletion_delay + 1)
    await gc_core.collect_garbage(client.app)
    # assert dynamic service 2,3 is removed
    calls = [
        mock.call(
            app=client.server.app,
            dynamic_service_stop=DynamicServiceStop(
                user_id=user_id,
                project_id=service2.project_id,
                node_id=service2.node_uuid,
                simcore_user_agent=UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE,
                save_state=expected_save_state,
            ),
            progress=mock.ANY,
        ),
        mock.call(
            app=client.server.app,
            dynamic_service_stop=DynamicServiceStop(
                user_id=user_id,
                project_id=service3.project_id,
                node_id=service3.node_uuid,
                simcore_user_agent=UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE,
                save_state=expected_save_state,
            ),
            progress=mock.ANY,
        ),
    ]
    mocked_dynamic_services_interface[
        "dynamic_scheduler.api.stop_dynamic_service"
    ].assert_has_calls(calls)
    mocked_dynamic_services_interface[
        "dynamic_scheduler.api.stop_dynamic_service"
    ].reset_mock()


@pytest.mark.xfail(
    reason="it is currently not permitted to open the same project from 2 different tabs"
)
@pytest.mark.parametrize(
    "user_role, expected_save_state",
    [
        # (UserRole.ANONYMOUS),
        # (UserRole.GUEST),
        (UserRole.USER, True),
        (UserRole.TESTER, True),
    ],
)
async def test_services_remain_after_closing_one_out_of_two_tabs(
    fast_service_deletion_delay: int,
    director_v2_service_mock: aioresponses,
    client,
    logged_user,
    empty_user_project,
    empty_user_project2,
    mocked_dynamic_services_interface,
    create_dynamic_service_mock: Callable[..., Awaitable[DynamicServiceGet]],
    create_socketio_connection: Callable,
    client_session_id_factory: Callable[[], str],
    expected_save_state: bool,
    open_project: Callable,
):
    # create server with delay set to DELAY
    service = await create_dynamic_service_mock(
        user_id=logged_user["id"], project_id=empty_user_project["uuid"]
    )
    # open project in tab1
    client_session_id1 = client_session_id_factory()
    sio1 = await create_socketio_connection(client_session_id1)
    assert sio1
    await open_project(client, empty_user_project["uuid"], client_session_id1)
    # open project in tab2
    client_session_id2 = client_session_id_factory()
    sio2 = await create_socketio_connection(client_session_id2)
    assert sio2
    await open_project(client, empty_user_project["uuid"], client_session_id2)
    # close project in tab1
    await close_project(client, empty_user_project["uuid"], client_session_id1)
    # wait the defined delay
    await asyncio.sleep(fast_service_deletion_delay + 1)
    await gc_core.collect_garbage(client.app)
    # assert dynamic service is still around
    mocked_dynamic_services_interface[
        "dynamic_scheduler.api.stop_dynamic_service"
    ].assert_not_called()
    # close project in tab2
    await close_project(client, empty_user_project["uuid"], client_session_id2)
    # wait the defined delay
    await asyncio.sleep(fast_service_deletion_delay + 1)
    await gc_core.collect_garbage(client.app)
    mocked_dynamic_services_interface[
        "dynamic_scheduler.api.stop_dynamic_service"
    ].assert_has_calls(
        [mock.call(client.server.app, service.node_uuid, expected_save_state)]
    )


@pytest.mark.parametrize(
    "user_role, expect_call, expected_save_state",
    [
        (UserRole.USER, False, True),
        (UserRole.TESTER, False, True),
        (UserRole.GUEST, True, False),
    ],
)
async def test_websocket_disconnected_remove_or_maintain_files_based_on_role(
    director_v2_service_mock: aioresponses,
    client,
    logged_user,
    empty_user_project,
    mocked_dynamic_services_interface,
    create_dynamic_service_mock: Callable[..., Awaitable[DynamicServiceGet]],
    client_session_id_factory: Callable[[], str],
    create_socketio_connection: Callable,
    # asyncpg_storage_system_mock,
    storage_subsystem_mock,  # when guest user logs out garbage is collected
    expect_call: bool,
    expected_save_state: bool,
    open_project: Callable,
    mocked_notifications_plugin: dict[str, mock.Mock],
):
    user_id = logged_user["id"]
    service = await create_dynamic_service_mock(
        user_id=user_id, project_id=empty_user_project["uuid"]
    )
    # create websocket
    client_session_id1 = client_session_id_factory()
    sio: socketio.AsyncClient = await create_socketio_connection(client_session_id1)
    assert sio
    # open project in client 1
    await open_project(client, empty_user_project["uuid"], client_session_id1)
    # logout
    logout_url = client.app.router["auth_logout"].url_for()
    r = await client.post(logout_url, json={"client_session_id": client_session_id1})
    assert r.url.path == logout_url.path
    await assert_status(r, status.HTTP_200_OK)

    # ensure sufficient time is wasted here
    await asyncio.sleep(SERVICE_DELETION_DELAY + 1)
    await gc_core.collect_garbage(client.app)

    # assert dynamic service is removed
    calls = [
        mock.call(
            app=client.server.app,
            dynamic_service_stop=DynamicServiceStop(
                user_id=user_id,
                project_id=service.project_id,
                simcore_user_agent=UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE,
                save_state=expected_save_state,
                node_id=service.node_uuid,
            ),
            progress=mock.ANY,
        )
    ]
    mocked_dynamic_services_interface[
        "dynamic_scheduler.api.stop_dynamic_service"
    ].assert_has_calls(calls)

    # this call is done async, so wait a bit here to ensure it is correctly done
    async for attempt in AsyncRetrying(**_TENACITY_ASSERT_RETRY):
        with attempt:
            if expect_call:
                # make sure `delete_project` is called
                storage_subsystem_mock[1].assert_called_once()
                # make sure `delete_user` is called
                # asyncpg_storage_system_mock.assert_called_once()
            else:
                # make sure `delete_project` not called
                storage_subsystem_mock[1].assert_not_called()
                # make sure `delete_user` not called
                # asyncpg_storage_system_mock.assert_not_called()
