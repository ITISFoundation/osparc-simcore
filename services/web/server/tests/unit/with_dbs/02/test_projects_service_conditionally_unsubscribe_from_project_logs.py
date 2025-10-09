# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=too-many-positional-arguments
# pylint: disable=too-many-statements
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=protected-access


import contextlib
from collections.abc import Awaitable, Callable

import pytest
import socketio
from aiohttp.test_utils import TestClient
from pytest_mock import MockerFixture, MockType
from pytest_simcore.helpers.webserver_login import log_client_in
from pytest_simcore.helpers.webserver_parametrizations import (
    ExpectedResponse,
    SocketHandlers,
)
from servicelib.aiohttp import status
from simcore_service_webserver.db.models import UserRole
from test_projects_states_handlers import _close_project, _open_project


@pytest.fixture
def max_number_of_user_sessions() -> int:
    return 3


@pytest.fixture
def mocked_publish_unsubscribe_from_project_logs_event(
    mocker: MockerFixture,
) -> MockType:
    import simcore_service_webserver.projects._projects_service  # noqa: PLC0415

    return mocker.patch.object(
        simcore_service_webserver.projects._projects_service,  # noqa: SLF001
        "_publish_unsubscribe_from_project_logs_event",
        autospec=True,
    )


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.USER, status.HTTP_200_OK),
    ],
)
async def test_conditionally_unsubscribe_from_project_logs(
    max_number_of_user_sessions: int,
    with_enabled_rtc_collaboration: None,
    client: TestClient,
    client_on_running_server_factory: Callable[[], TestClient],
    logged_user: dict,
    shared_project: dict,
    user_role: UserRole,
    expected: ExpectedResponse,
    exit_stack: contextlib.AsyncExitStack,
    create_socketio_connection_with_handlers: Callable[
        [str | None, TestClient],
        Awaitable[tuple[socketio.AsyncClient, str, SocketHandlers]],
    ],
    mocked_dynamic_services_interface: dict[str, MockType],
    mocked_publish_unsubscribe_from_project_logs_event: MockType,
    mock_catalog_api: dict[str, MockType],
    mocker: MockerFixture,
):
    # Use-case: 2 users open the same shared project, then close it
    # Only when the last user closes the project, the unsubscribe from project logs is done
    # (this is important to avoid loosing logs when multiple users are working on the same project)

    client_1 = client
    client_2 = client_on_running_server_factory()

    # 1. user 1 opens project
    sio1, client_id1, sio1_handlers = await create_socketio_connection_with_handlers(
        None, client_1
    )
    await _open_project(
        client_1,
        client_id1,
        shared_project,
        status.HTTP_200_OK,
    )

    # 2. create a separate client now and log in user2, open the same shared project
    user_2 = await log_client_in(
        client_2,
        {"role": user_role.name},
        enable_check=True,
        exit_stack=exit_stack,
    )
    sio2, client_id2, sio2_handlers = await create_socketio_connection_with_handlers(
        None, client_2
    )
    await _open_project(
        client_2,
        client_id2,
        shared_project,
        status.HTTP_200_OK,
    )

    # 3. user 1 closes the project (As user 2 is still connected, no unsubscribe should happen)
    await _close_project(
        client_1, client_id1, shared_project, status.HTTP_204_NO_CONTENT
    )
    assert not mocked_publish_unsubscribe_from_project_logs_event.called

    # 4. user 2 closes the project (now unsubscribe should happen)
    await _close_project(
        client_2, client_id2, shared_project, status.HTTP_204_NO_CONTENT
    )
    assert mocked_publish_unsubscribe_from_project_logs_event.called
