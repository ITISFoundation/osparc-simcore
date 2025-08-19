# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

"""
Tests for patch_project_and_notify_users function focusing on the Redis locking mechanism
and concurrent access patterns.
"""

import asyncio
from http import HTTPStatus
from typing import Any
from uuid import uuid4

import pytest
from aiohttp.test_utils import TestClient
from faker import Faker
from models_library.projects import ProjectID
from pytest_simcore.helpers.webserver_users import UserInfoDict
from servicelib.aiohttp import status
from servicelib.redis import increment_and_return_project_document_version
from simcore_service_webserver.db.models import UserRole
from simcore_service_webserver.projects._projects_service import (
    patch_project_and_notify_users,
)
from simcore_service_webserver.projects.models import ProjectDict
from simcore_service_webserver.redis import get_redis_document_manager_client_sdk


@pytest.fixture
def concurrent_patch_data_list(faker: Faker) -> list[dict[str, Any]]:
    """Generate multiple different patch data for concurrent testing"""
    return [{"name": f"concurrent-test-{faker.word()}-{i}"} for i in range(10)]


@pytest.fixture
def user_primary_gid(logged_user: UserInfoDict) -> int:
    """Extract user primary group ID from logged user"""
    return int(logged_user["primary_gid"])


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.USER, status.HTTP_200_OK),
    ],
)
async def test_patch_project_and_notify_users_sequential(
    user_role: UserRole,
    with_enabled_rtc_collaboration: None,
    expected: HTTPStatus,
    client: TestClient,
    user_project: ProjectDict,
    user_primary_gid: int,
    faker: Faker,
):
    """Test that patch_project_and_notify_users works correctly in sequential mode"""
    assert client.app
    project_uuid = ProjectID(user_project["uuid"])

    # Perform sequential patches
    patch_data_1 = {"name": f"sequential-test-{faker.word()}-1"}
    patch_data_2 = {"name": f"sequential-test-{faker.word()}-2"}

    # First patch
    await patch_project_and_notify_users(
        app=client.app,
        project_uuid=project_uuid,
        patch_project_data=patch_data_1,
        user_primary_gid=user_primary_gid,
        client_session_id=None,
    )

    # Get version after first patch
    redis_client = get_redis_document_manager_client_sdk(client.app)
    version_1 = await increment_and_return_project_document_version(
        redis_client=redis_client, project_uuid=project_uuid
    )

    # Second patch
    await patch_project_and_notify_users(
        app=client.app,
        project_uuid=project_uuid,
        patch_project_data=patch_data_2,
        user_primary_gid=user_primary_gid,
        client_session_id=None,
    )

    # Get version after second patch
    version_2 = await increment_and_return_project_document_version(
        redis_client=redis_client, project_uuid=project_uuid
    )

    # Verify versions are incrementing correctly
    assert version_2 > version_1
    assert version_2 - version_1 == 2  # Two operations should increment by 2


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.USER, status.HTTP_200_OK),
    ],
)
async def test_patch_project_and_notify_users_concurrent_locking(
    user_role: UserRole,
    with_enabled_rtc_collaboration: None,
    expected: HTTPStatus,
    client: TestClient,
    user_project: ProjectDict,
    user_primary_gid: int,
    concurrent_patch_data_list: list[dict[str, Any]],
):
    """Test that patch_project_and_notify_users handles concurrent access correctly with locking"""
    assert client.app
    project_uuid = ProjectID(user_project["uuid"])

    # Get initial version
    redis_client = get_redis_document_manager_client_sdk(client.app)
    initial_version = await increment_and_return_project_document_version(
        redis_client=redis_client, project_uuid=project_uuid
    )

    # Create concurrent patch tasks
    tasks = [
        patch_project_and_notify_users(
            app=client.app,
            project_uuid=project_uuid,
            patch_project_data=patch_data,
            user_primary_gid=user_primary_gid,
            client_session_id=None,
        )
        for patch_data in concurrent_patch_data_list
    ]

    # Execute all tasks concurrently
    await asyncio.gather(*tasks)

    # Get final version
    final_version = await increment_and_return_project_document_version(
        redis_client=redis_client, project_uuid=project_uuid
    )

    # Verify that all concurrent operations were processed and version incremented correctly
    # Each patch_project_and_notify_users call should increment version by 1
    expected_final_version = initial_version + len(concurrent_patch_data_list) + 1
    assert final_version == expected_final_version


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.USER, status.HTTP_200_OK),
    ],
)
async def test_patch_project_and_notify_users_concurrent_different_projects(
    user_role: UserRole,
    with_enabled_rtc_collaboration: None,
    expected: HTTPStatus,
    client: TestClient,
    user_project: ProjectDict,
    user_primary_gid: int,
    faker: Faker,
):
    """Test that concurrent patches to different projects don't interfere with each other"""
    assert client.app

    # Use different project UUIDs to simulate different projects
    project_uuid_1 = ProjectID(user_project["uuid"])
    project_uuid_2 = ProjectID(str(uuid4()))  # Simulate second project
    project_uuid_3 = ProjectID(str(uuid4()))  # Simulate third project

    redis_client = get_redis_document_manager_client_sdk(client.app)

    # Get initial versions
    initial_version_1 = await increment_and_return_project_document_version(
        redis_client=redis_client, project_uuid=project_uuid_1
    )
    initial_version_2 = await increment_and_return_project_document_version(
        redis_client=redis_client, project_uuid=project_uuid_2
    )
    initial_version_3 = await increment_and_return_project_document_version(
        redis_client=redis_client, project_uuid=project_uuid_3
    )

    # Note: For this test, we only test the locking mechanism for project_1
    # as we would need to create actual projects for the others
    patch_data = {"name": f"concurrent-different-projects-{faker.word()}"}

    # Only test project_1 (real project) but verify version isolation
    await patch_project_and_notify_users(
        app=client.app,
        project_uuid=project_uuid_1,
        patch_project_data=patch_data,
        user_primary_gid=user_primary_gid,
        client_session_id=None,
    )

    # Get final versions
    final_version_1 = await increment_and_return_project_document_version(
        redis_client=redis_client, project_uuid=project_uuid_1
    )
    final_version_2 = await increment_and_return_project_document_version(
        redis_client=redis_client, project_uuid=project_uuid_2
    )
    final_version_3 = await increment_and_return_project_document_version(
        redis_client=redis_client, project_uuid=project_uuid_3
    )

    # Verify that only project_1 version changed
    assert final_version_1 == initial_version_1 + 2  # One patch + one version check
    assert final_version_2 == initial_version_2 + 1  # Only version check
    assert final_version_3 == initial_version_3 + 1  # Only version check
