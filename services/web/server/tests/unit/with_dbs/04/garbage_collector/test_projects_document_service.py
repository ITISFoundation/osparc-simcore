# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import uuid
from typing import Any

import pytest
from aiohttp.test_utils import TestClient
from common_library.users_enums import UserRole
from models_library.projects import ProjectID
from pytest_simcore.helpers.webserver_users import UserInfoDict
from servicelib.redis._project_document_version import (
    increment_and_return_project_document_version,
)
from simcore_service_webserver.projects import _project_document_service

pytest_simcore_core_services_selection = [
    "redis",
]

pytest_simcore_ops_services_selection = [
    "redis-commander",
]


@pytest.fixture
def sample_project_uuids() -> list[ProjectID]:
    """Generate sample project UUIDs for testing."""
    return [
        ProjectID(str(uuid.uuid4())),
        ProjectID(str(uuid.uuid4())),
        ProjectID(str(uuid.uuid4())),
    ]


@pytest.mark.parametrize(
    "user_role",
    [
        UserRole.USER,
    ],
)
async def test_remove_project_documents_as_admin_with_real_connections(
    client: TestClient,
    logged_user: UserInfoDict,
    redis_client: Any,  # Real Redis client from conftest
    sample_project_uuids: list[ProjectID],
    create_socketio_connection: Any,  # Real SocketIO connection factory
):
    """Test removing project documents with real Redis and SocketIO connections."""
    from models_library.api_schemas_webserver.socketio import SocketIORoomStr
    from simcore_service_webserver.projects._project_document_service import (
        get_redis_document_manager_client_sdk,
    )
    from simcore_service_webserver.socketio._utils import get_socket_server

    # Get the real Redis document manager client
    redis_document_client = get_redis_document_manager_client_sdk(client.app)

    # Get the real SocketIO server
    sio_server = get_socket_server(client.app)

    # Setup: Create real Redis keys for project documents
    test_keys = []
    for project_id in sample_project_uuids:
        key = f"projects:{project_id}:version"
        test_keys.append(key)
        # Set a dummy document version in Redis
        # await redis_document_client.redis.set(key, "1.0")
        await increment_and_return_project_document_version(
            redis_client=redis_document_client, project_uuid=project_id
        )
        await increment_and_return_project_document_version(
            redis_client=redis_document_client, project_uuid=project_id
        )
    # # Also add some invalid keys that should be ignored
    # await redis_document_client.redis.set("projects:invalid-uuid:version", "1.0")
    # await redis_document_client.redis.set("other:key:pattern", "1.0")

    # Verify keys exist before cleanup
    for key in test_keys:
        assert await redis_document_client.redis.exists(key) == 1

    # Create SocketIO connections for some projects (simulating users working on projects)
    connections = []

    # Connect a user to the first project room
    sio_client_1, session_id_1 = await create_socketio_connection(None, client)
    project_room_1 = SocketIORoomStr.from_project_id(sample_project_uuids[0])
    await sio_server.enter_room(sio_client_1.get_sid(), project_room_1)
    connections.append((sio_client_1, session_id_1))

    # Connect another user to the second project room
    sio_client_2, session_id_2 = await create_socketio_connection(None, client)
    project_room_2 = SocketIORoomStr.from_project_id(sample_project_uuids[1])
    await sio_server.enter_room(sio_client_2.get_sid(), project_room_2)
    connections.append((sio_client_2, session_id_2))

    # Third project has no connected users (sio_client_3 not added to project room)
    sio_client_3, session_id_3 = await create_socketio_connection(None, client)
    connections.append((sio_client_3, session_id_3))

    try:
        # Execute the function under test
        await _project_document_service.remove_project_documents_as_admin(client.app)

        # Verify results:
        # - Projects 0 and 1 should still have their documents (users connected)
        # - Project 2 should have its document removed (no users connected)
        assert (
            await redis_document_client.redis.exists(
                f"projects:{sample_project_uuids[0]}:version"
            )
            == 1
        )
        assert (
            await redis_document_client.redis.exists(
                f"projects:{sample_project_uuids[1]}:version"
            )
            == 1
        )
        assert (
            await redis_document_client.redis.exists(
                f"projects:{sample_project_uuids[2]}:version"
            )
            == 0
        )

        # Invalid keys should remain untouched
        # assert await redis_document_client.redis.exists("projects:invalid-uuid:version") == 1
        # assert await redis_document_client.redis.exists("other:key:pattern") == 1

    finally:
        # Cleanup: Disconnect all SocketIO clients
        for sio_client, _ in connections:
            if sio_client.connected:
                await sio_client.disconnect()

        # Cleanup: Remove test keys from Redis
        for key in test_keys:
            await redis_document_client.redis.delete(key)
        # await redis_document_client.redis.delete("projects:invalid-uuid:version")
        # await redis_document_client.redis.delete("other:key:pattern")


# async def test_remove_project_documents_as_admin_with_connected_users(
#     client: TestClient,
#     logged_user: UserInfoDict,
#     mock_redis_client: tuple[Any, Any],
#     mock_socketio_server: tuple[Any, Any],
#     redis_keys_with_projects: list[str],
#     sample_project_uuids: list[ProjectID],
#     mocker: MockerFixture,
# ):
#     """Test that project documents are NOT removed when users are connected to project rooms."""
#     redis_client_sdk, redis_client = mock_redis_client
#     sio_server, sio_manager = mock_socketio_server

#     # Mock dependencies
#     mocker.patch(
#         "simcore_service_webserver.projects._project_document_service.get_redis_document_manager_client_sdk",
#         return_value=redis_client_sdk,
#     )
#     mocker.patch(
#         "simcore_service_webserver.projects._project_document_service.get_socket_server",
#         return_value=sio_server,
#     )

#     # Mock Redis scan_iter to return our test keys
#     async def mock_scan_iter(match=None, count=None):
#         for key in redis_keys_with_projects:
#             if match and "*" in match:
#                 pattern = match.replace("*", "")
#                 if pattern in key:
#                     yield key
#             else:
#                 yield key

#     redis_client.scan_iter = mock_scan_iter

#     # Mock socketio room participants - simulate connected users for all projects
#     sio_manager.get_participants.return_value = [
#         ("session_id_1", "socket_id_1"),
#         ("session_id_2", "socket_id_2"),
#     ]

#     # Mock Redis delete operation
#     redis_client.delete = AsyncMock()

#     # Execute the function
#     await _project_document_service.remove_project_documents_as_admin(client.app)

#     # Verify that get_participants was called for each valid project UUID
#     expected_calls = [
#         mocker.call(
#             namespace="/", room=SocketIORoomStr.from_project_id(project_id)
#         )
#         for project_id in sample_project_uuids
#     ]
#     sio_manager.get_participants.assert_has_calls(expected_calls, any_order=True)

#     # Verify that delete was NOT called (users are connected)
#     redis_client.delete.assert_not_called()


# async def test_remove_project_documents_as_admin_mixed_connectivity(
#     client: TestClient,
#     logged_user: UserInfoDict,
#     mock_redis_client: tuple[Any, Any],
#     mock_socketio_server: tuple[Any, Any],
#     sample_project_uuids: list[ProjectID],
#     mocker: MockerFixture,
# ):
#     """Test mixed scenario where some projects have connected users and others don't."""
#     redis_client_sdk, redis_client = mock_redis_client
#     sio_server, sio_manager = mock_socketio_server

#     # Create test keys for our projects
#     redis_keys = [f"projects:{project_id}:version" for project_id in sample_project_uuids]

#     # Mock dependencies
#     mocker.patch(
#         "simcore_service_webserver.projects._project_document_service.get_redis_document_manager_client_sdk",
#         return_value=redis_client_sdk,
#     )
#     mocker.patch(
#         "simcore_service_webserver.projects._project_document_service.get_socket_server",
#         return_value=sio_server,
#     )

#     # Mock Redis scan_iter
#     async def mock_scan_iter(match=None, count=None):
#         for key in redis_keys:
#             yield key

#     redis_client.scan_iter = mock_scan_iter

#     # Mock socketio room participants - first project has users, others don't
#     def mock_get_participants(namespace, room):
#         project_room_0 = SocketIORoomStr.from_project_id(sample_project_uuids[0])
#         if room == project_room_0:
#             return [("session_id_1", "socket_id_1")]  # Has connected users
#         return []  # No connected users

#     sio_manager.get_participants.side_effect = mock_get_participants

#     # Mock Redis delete operation
#     redis_client.delete = AsyncMock()

#     # Execute the function
#     await _project_document_service.remove_project_documents_as_admin(client.app)

#     # Verify that delete was called only for projects without connected users (2 out of 3)
#     assert redis_client.delete.call_count == 2
#     redis_client.delete.assert_any_call(f"projects:{sample_project_uuids[1]}:version")
#     redis_client.delete.assert_any_call(f"projects:{sample_project_uuids[2]}:version")


# async def test_remove_project_documents_as_admin_invalid_uuids(
#     client: TestClient,
#     logged_user: UserInfoDict,
#     mock_redis_client: tuple[Any, Any],
#     mock_socketio_server: tuple[Any, Any],
#     mocker: MockerFixture,
# ):
#     """Test that invalid UUID patterns are skipped."""
#     redis_client_sdk, redis_client = mock_redis_client
#     sio_server, sio_manager = mock_socketio_server

#     # Mock dependencies
#     mocker.patch(
#         "simcore_service_webserver.projects._project_document_service.get_redis_document_manager_client_sdk",
#         return_value=redis_client_sdk,
#     )
#     mocker.patch(
#         "simcore_service_webserver.projects._project_document_service.get_socket_server",
#         return_value=sio_server,
#     )

#     # Redis keys with invalid patterns
#     invalid_keys = [
#         "projects:invalid-uuid-format:version",
#         "projects:not-a-uuid:version",
#         "other:pattern:version",
#         "projects::version",  # empty UUID
#     ]

#     # Mock Redis scan_iter
#     async def mock_scan_iter(match=None, count=None):
#         for key in invalid_keys:
#             yield key

#     redis_client.scan_iter = mock_scan_iter

#     # Mock Redis delete operation
#     redis_client.delete = AsyncMock()

#     # Execute the function
#     await _project_document_service.remove_project_documents_as_admin(client.app)

#     # Verify that get_participants was never called (no valid UUIDs)
#     sio_manager.get_participants.assert_not_called()

#     # Verify that delete was never called (no valid projects)
#     redis_client.delete.assert_not_called()


# async def test_remove_project_documents_as_admin_socketio_errors(
#     client: TestClient,
#     logged_user: UserInfoDict,
#     mock_redis_client: tuple[Any, Any],
#     mock_socketio_server: tuple[Any, Any],
#     sample_project_uuids: list[ProjectID],
#     mocker: MockerFixture,
# ):
#     """Test handling of SocketIO errors when checking room participants."""
#     redis_client_sdk, redis_client = mock_redis_client
#     sio_server, sio_manager = mock_socketio_server

#     # Create test keys
#     redis_keys = [f"projects:{sample_project_uuids[0]}:version"]

#     # Mock dependencies
#     mocker.patch(
#         "simcore_service_webserver.projects._project_document_service.get_redis_document_manager_client_sdk",
#         return_value=redis_client_sdk,
#     )
#     mocker.patch(
#         "simcore_service_webserver.projects._project_document_service.get_socket_server",
#         return_value=sio_server,
#     )

#     # Mock Redis scan_iter
#     async def mock_scan_iter(match=None, count=None):
#         for key in redis_keys:
#             yield key

#     redis_client.scan_iter = mock_scan_iter

#     # Mock socketio room participants to raise an error
#     sio_manager.get_participants.side_effect = KeyError("Room not found")

#     # Mock Redis delete operation
#     redis_client.delete = AsyncMock()

#     # Execute the function - should not raise an exception
#     await _project_document_service.remove_project_documents_as_admin(client.app)

#     # Verify that get_participants was called
#     sio_manager.get_participants.assert_called_once()

#     # Verify that delete was not called due to the error
#     redis_client.delete.assert_not_called()


# async def test_remove_project_documents_as_admin_empty_redis(
#     client: TestClient,
#     logged_user: UserInfoDict,
#     mock_redis_client: tuple[Any, Any],
#     mock_socketio_server: tuple[Any, Any],
#     mocker: MockerFixture,
# ):
#     """Test function behavior when Redis has no matching keys."""
#     redis_client_sdk, redis_client = mock_redis_client
#     sio_server, sio_manager = mock_socketio_server

#     # Mock dependencies
#     mocker.patch(
#         "simcore_service_webserver.projects._project_document_service.get_redis_document_manager_client_sdk",
#         return_value=redis_client_sdk,
#     )
#     mocker.patch(
#         "simcore_service_webserver.projects._project_document_service.get_socket_server",
#         return_value=sio_server,
#     )

#     # Mock Redis scan_iter to return no keys
#     async def mock_scan_iter(match=None, count=None):
#         return
#         yield  # This line will never execute, making it an empty generator

#     redis_client.scan_iter = mock_scan_iter

#     # Mock Redis delete operation
#     redis_client.delete = AsyncMock()

#     # Execute the function
#     await _project_document_service.remove_project_documents_as_admin(client.app)

#     # Verify that get_participants was never called (no keys found)
#     sio_manager.get_participants.assert_not_called()

#     # Verify that delete was never called (no keys to delete)
#     redis_client.delete.assert_not_called()


# async def test_remove_project_documents_as_admin_logging(
#     client: TestClient,
#     logged_user: UserInfoDict,
#     mock_redis_client: tuple[Any, Any],
#     mock_socketio_server: tuple[Any, Any],
#     sample_project_uuids: list[ProjectID],
#     mocker: MockerFixture,
#     caplog: pytest.LogCaptureFixture,
# ):
#     """Test that appropriate log messages are generated."""
#     redis_client_sdk, redis_client = mock_redis_client
#     sio_server, sio_manager = mock_socketio_server

#     # Create test keys - one project without users, one with users
#     redis_keys = [
#         f"projects:{sample_project_uuids[0]}:version",
#         f"projects:{sample_project_uuids[1]}:version",
#     ]

#     # Mock dependencies
#     mocker.patch(
#         "simcore_service_webserver.projects._project_document_service.get_redis_document_manager_client_sdk",
#         return_value=redis_client_sdk,
#     )
#     mocker.patch(
#         "simcore_service_webserver.projects._project_document_service.get_socket_server",
#         return_value=sio_server,
#     )

#     # Mock Redis scan_iter
#     async def mock_scan_iter(match=None, count=None):
#         for key in redis_keys:
#             yield key

#     redis_client.scan_iter = mock_scan_iter

#     # Mock socketio room participants - first project has no users, second has users
#     def mock_get_participants(namespace, room):
#         project_room_0 = SocketIORoomStr.from_project_id(sample_project_uuids[0])
#         if room == project_room_0:
#             return []  # No connected users
#         return [("session_id_1", "socket_id_1")]  # Has connected users

#     sio_manager.get_participants.side_effect = mock_get_participants

#     # Mock Redis delete operation
#     redis_client.delete = AsyncMock()

#     # Execute the function
#     import logging
#     with caplog.at_level(logging.DEBUG):
#         await _project_document_service.remove_project_documents_as_admin(client.app)

#     # Check that info log was generated for removed project
#     info_logs = [record for record in caplog.records if record.levelname == "INFO"]
#     assert any(
#         "Removed project document for project" in record.message
#         and str(sample_project_uuids[0]) in record.message
#         for record in info_logs
#     )

#     # Check that completion log was generated
#     assert any(
#         "Project document cleanup completed: removed 1 project documents" in record.message
#         for record in info_logs
#     )

#     # Check that debug log was generated for project with connected users
#     debug_logs = [record for record in caplog.records if record.levelname == "DEBUG"]
#     assert any(
#         "has" in record.message
#         and "connected users, keeping document" in record.message
#         and str(sample_project_uuids[1]) in record.message
#         for record in debug_logs
#     )
