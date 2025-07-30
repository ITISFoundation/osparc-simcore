# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import uuid
from collections.abc import AsyncGenerator
from typing import Any

import pytest
from aiohttp.test_utils import TestClient
from common_library.users_enums import UserRole
from models_library.api_schemas_webserver.socketio import SocketIORoomStr
from models_library.projects import ProjectID
from pytest_simcore.helpers.webserver_users import UserInfoDict
from servicelib.redis._project_document_version import (
    increment_and_return_project_document_version,
)
from simcore_service_webserver.projects import _project_document_service
from simcore_service_webserver.projects._project_document_service import (
    get_redis_document_manager_client_sdk,
)
from simcore_service_webserver.socketio._utils import get_socket_server

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


@pytest.fixture
def redis_document_client(client: TestClient) -> Any:
    """Get Redis document manager client for testing."""
    return get_redis_document_manager_client_sdk(client.app)


@pytest.fixture
def socketio_server(client: TestClient) -> Any:
    """Get SocketIO server instance for testing."""
    return get_socket_server(client.app)


@pytest.fixture
async def project_documents_setup(
    redis_document_client: Any, sample_project_uuids: list[ProjectID]
) -> AsyncGenerator[list[str], None]:
    """Setup project documents in Redis and cleanup after test."""
    test_keys = []

    # Setup: Create project document versions in Redis
    for project_id in sample_project_uuids:
        key = f"projects:{project_id}:version"
        test_keys.append(key)
        # Create document versions (calling twice to increment to version 2)
        await increment_and_return_project_document_version(
            redis_client=redis_document_client, project_uuid=project_id
        )
        await increment_and_return_project_document_version(
            redis_client=redis_document_client, project_uuid=project_id
        )

    # Verify keys exist before returning
    for key in test_keys:
        assert await redis_document_client.redis.exists(key) == 1

    yield test_keys

    # Cleanup: Remove test keys from Redis
    for key in test_keys:
        await redis_document_client.redis.delete(key)


@pytest.fixture
async def create_project_socketio_connections(
    create_socketio_connection: Any, client: TestClient, socketio_server: Any
):
    """Factory fixture to create SocketIO connections with automatic cleanup."""
    connections = []

    async def _create_connections_for_projects(
        project_uuids: list[ProjectID], connected_project_indices: list[int]
    ) -> list[tuple[Any, str]]:
        """Create SocketIO connections and connect specified projects to their rooms.

        Args:
            project_uuids: List of project UUIDs
            connected_project_indices: Indices of projects that should be connected to rooms

        Returns:
            List of (sio_client, session_id) tuples
        """
        created_connections = []

        for i, project_id in enumerate(project_uuids):
            sio_client, session_id = await create_socketio_connection(None, client)
            created_connections.append((sio_client, session_id))

            # Connect to project room if this project index is in the connected list
            if i in connected_project_indices:
                project_room = SocketIORoomStr.from_project_id(project_id)
                await socketio_server.enter_room(sio_client.get_sid(), project_room)

        connections.extend(created_connections)
        return created_connections

    yield _create_connections_for_projects

    # Cleanup: Disconnect all SocketIO clients
    for sio_client, _ in connections:
        if sio_client.connected:
            await sio_client.disconnect()


@pytest.mark.parametrize(
    "user_role",
    [
        UserRole.USER,
    ],
)
async def test_remove_project_documents_as_admin_with_real_connections(
    client: TestClient,
    logged_user: UserInfoDict,
    redis_document_client: Any,
    sample_project_uuids: list[ProjectID],
    project_documents_setup: list[str],
    create_project_socketio_connections,
):
    """Test removing project documents with real Redis and SocketIO connections.

    Test scenario:
    - Project 0: Has SocketIO connection -> should be preserved
    - Project 1: Has SocketIO connection -> should be preserved
    - Project 2: No SocketIO connection -> should be removed
    """
    # Create SocketIO connections - connect first two projects to their rooms
    await create_project_socketio_connections(
        project_uuids=sample_project_uuids,
        connected_project_indices=[0, 1],  # Connect projects 0 and 1 to rooms
    )

    # Execute the function being tested
    await _project_document_service.remove_project_documents_as_admin(client.app)

    # Verify results:
    # Projects 0 and 1 should still have their documents (users connected)
    assert (
        await redis_document_client.redis.exists(
            f"projects:{sample_project_uuids[0]}:version"
        )
        == 1
    ), "Project 0 should be preserved because it has active SocketIO connection"

    assert (
        await redis_document_client.redis.exists(
            f"projects:{sample_project_uuids[1]}:version"
        )
        == 1
    ), "Project 1 should be preserved because it has active SocketIO connection"

    # Project 2 should have its document removed (no users connected)
    assert (
        await redis_document_client.redis.exists(
            f"projects:{sample_project_uuids[2]}:version"
        )
        == 0
    ), "Project 2 should be removed because it has no active SocketIO connections"


@pytest.mark.parametrize(
    "user_role",
    [
        UserRole.USER,
    ],
)
async def test_remove_project_documents_as_admin_with_known_opened_projects(
    client: TestClient,
    logged_user: UserInfoDict,
    redis_document_client: Any,
    sample_project_uuids: list[ProjectID],
    project_documents_setup: list[str],
    mocker,
):
    """Test that project documents are NOT removed when projects are in known opened projects list.

    Test scenario:
    - Projects 0 and 1: In known opened projects list -> should be preserved
    - Project 2: Not in known opened projects and no connections -> should be removed
    """
    # Mock list_opened_project_ids to return the first two projects as "known opened"
    known_opened_projects = sample_project_uuids[:2]  # First two projects are "opened"
    mocker.patch(
        "simcore_service_webserver.projects._project_document_service.list_opened_project_ids",
        return_value=known_opened_projects,
    )

    # Execute the function being tested
    await _project_document_service.remove_project_documents_as_admin(client.app)

    # Verify results: Projects 0 and 1 should be preserved, Project 2 should be removed
    assert (
        await redis_document_client.redis.exists(
            f"projects:{sample_project_uuids[0]}:version"
        )
        == 1
    ), "Project 0 should be kept because it's in known opened projects"

    assert (
        await redis_document_client.redis.exists(
            f"projects:{sample_project_uuids[1]}:version"
        )
        == 1
    ), "Project 1 should be kept because it's in known opened projects"

    assert (
        await redis_document_client.redis.exists(
            f"projects:{sample_project_uuids[2]}:version"
        )
        == 0
    ), "Project 2 should be removed because it's not in known opened projects and has no socket connections"


@pytest.mark.parametrize(
    "user_role",
    [
        UserRole.USER,
    ],
)
async def test_remove_project_documents_as_admin_mixed_state(
    client: TestClient,
    logged_user: UserInfoDict,
    redis_document_client: Any,
    sample_project_uuids: list[ProjectID],
    create_project_socketio_connections,
):
    """Test mixed state: some projects have documents, some have connections without documents."""
    # Setup: Create document only for first project
    test_key = f"projects:{sample_project_uuids[0]}:version"
    await increment_and_return_project_document_version(
        redis_client=redis_document_client, project_uuid=sample_project_uuids[0]
    )

    # Create SocketIO connection for second project (no document)
    await create_project_socketio_connections(
        project_uuids=sample_project_uuids[1:2],  # Only second project
        connected_project_indices=[0],  # Connect it to room
    )

    # Execute the function
    await _project_document_service.remove_project_documents_as_admin(client.app)

    # Verify: First project document should be removed (no connections)
    assert (
        await redis_document_client.redis.exists(test_key) == 0
    ), "Project 0 document should be removed (no active connections)"

    # Cleanup
    await redis_document_client.redis.delete(test_key)
