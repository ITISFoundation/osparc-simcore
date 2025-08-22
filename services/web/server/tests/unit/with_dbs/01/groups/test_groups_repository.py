# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from collections.abc import AsyncGenerator, Callable, Coroutine
from typing import Any

import pytest
from aiohttp.test_utils import TestClient
from models_library.groups import GroupMember, StandardGroupCreate
from pytest_simcore.helpers.webserver_users import UserInfoDict
from simcore_postgres_database.models.users import UserRole
from simcore_service_webserver.groups._groups_repository import (
    create_standard_group,
    delete_standard_group,
    list_users_in_group,
)


@pytest.fixture
async def create_test_group(
    client: TestClient, logged_user: UserInfoDict
) -> AsyncGenerator[Callable[..., Coroutine[Any, Any, Any]], None]:
    """Fixture that creates a standard group and ensures cleanup."""
    created_groups = []

    async def _create_group(
        name: str = "Test Group",
        description: str = "A test group",
        thumbnail: str | None = None,
    ):
        group, _ = await create_standard_group(
            app=client.app,
            user_id=logged_user["id"],
            create=StandardGroupCreate(
                name=name,
                description=description,
                thumbnail=thumbnail,
            ),
        )
        created_groups.append(group)
        return group

    yield _create_group

    # Cleanup all created groups
    for group in created_groups:
        await delete_standard_group(
            app=client.app, user_id=logged_user["id"], group_id=group.gid
        )


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_list_users_in_group_owner_only(
    client: TestClient,
    user_role: UserRole,
    logged_user: UserInfoDict,
    create_test_group,
):
    """Test list_users_in_group returns only the owner for a new group."""
    assert client.app

    # Create a standard group
    group = await create_test_group(
        name="Test Owner Only Group",
        description="A test group to check owner-only user list",
    )

    # List users in the group - should only contain the owner
    users_in_group = await list_users_in_group(app=client.app, group_id=group.gid)

    # Should contain exactly one user (the owner)
    assert len(users_in_group) == 1
    assert isinstance(users_in_group[0], GroupMember)
    assert users_in_group[0].id == logged_user["id"]
