# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

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


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_list_users_in_group_owner_only(
    client: TestClient,
    user_role: UserRole,
    logged_user: UserInfoDict,
):
    """Test list_users_in_group returns only the owner for a new group."""
    assert client.app

    # Create a standard group
    group, _ = await create_standard_group(
        app=client.app,
        user_id=logged_user["id"],
        create=StandardGroupCreate(
            name="Test Owner Only Group",
            description="A test group to check owner-only user list",
            thumbnail=None,
        ),
    )

    try:
        # List users in the group - should only contain the owner
        users_in_group = await list_users_in_group(app=client.app, group_id=group.gid)

        # Should contain exactly one user (the owner)
        assert len(users_in_group) == 1
        assert isinstance(users_in_group[0], GroupMember)
        assert users_in_group[0].id == logged_user["id"]

    finally:
        # Clean up
        await delete_standard_group(
            app=client.app, user_id=logged_user["id"], group_id=group.gid
        )
