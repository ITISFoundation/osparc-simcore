# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements


from http import HTTPStatus

import pytest
from aiohttp.test_utils import TestClient
from models_library.api_schemas_webserver.projects_access_rights import (
    ProjectShareAccepted,
)
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.webserver_users import NewUser, UserInfoDict
from servicelib.aiohttp import status
from simcore_service_webserver.db.models import UserRole
from simcore_service_webserver.projects.models import ProjectDict


@pytest.mark.acceptance_test(
    "Driving test for https://github.com/ITISFoundation/osparc-issues/issues/1547"
)
@pytest.mark.parametrize("user_role,expected", [(UserRole.USER, status.HTTP_200_OK)])
async def test_projects_groups_full_workflow(  # noqa: PLR0915
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    expected: HTTPStatus,
):
    assert client.app
    # check the default project permissions
    url = client.app.router["list_project_groups"].url_for(
        project_id=f"{user_project['uuid']}"
    )
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert len(data) == 1
    assert data[0]["gid"] == logged_user["primary_gid"]
    assert data[0]["read"] is True
    assert data[0]["write"] is True
    assert data[0]["delete"] is True

    # Get project endpoint and check permissions
    url = client.app.router["get_project"].url_for(
        project_id=f"{user_project['uuid']}",
    )
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert len(data["accessRights"]) == 1
    assert data["accessRights"] == {
        f"{logged_user['primary_gid']}": {"read": True, "write": True, "delete": True}
    }

    # List project endpoint and check permissions
    url = client.app.router["list_projects"].url_for()
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert len(data[0]["accessRights"]) == 1
    assert data[0]["accessRights"] == {
        f"{logged_user['primary_gid']}": {"read": True, "write": True, "delete": True}
    }

    async with NewUser(
        app=client.app,
    ) as new_user:
        # We add new user to the project
        url = client.app.router["create_project_group"].url_for(
            project_id=f"{user_project['uuid']}",
            group_id=f"{new_user['primary_gid']}",
        )
        resp = await client.post(
            f"{url}", json={"read": True, "write": False, "delete": False}
        )
        data, _ = await assert_status(resp, status.HTTP_201_CREATED)

        # Check the project permissions of added user
        url = client.app.router["list_project_groups"].url_for(
            project_id=f"{user_project['uuid']}"
        )
        resp = await client.get(f"{url}")
        data, _ = await assert_status(resp, status.HTTP_200_OK)
        assert len(data) == 2
        assert data[1]["gid"] == new_user["primary_gid"]
        assert data[1]["read"] is True
        assert data[1]["write"] is False
        assert data[1]["delete"] is False

        # Get the project endpoint and check the permissions
        url = client.app.router["get_project"].url_for(
            project_id=f"{user_project['uuid']}",
        )
        resp = await client.get(f"{url}")
        data, _ = await assert_status(resp, status.HTTP_200_OK)
        assert len(data["accessRights"]) == 2
        assert data["accessRights"] == {
            f"{logged_user['primary_gid']}": {
                "read": True,
                "write": True,
                "delete": True,
            },
            f"{new_user['primary_gid']}": {
                "read": True,
                "write": False,
                "delete": False,
            },
        }

        # List project endpoint and check permissions
        url = client.app.router["list_projects"].url_for()
        resp = await client.get(f"{url}")
        data, _ = await assert_status(resp, status.HTTP_200_OK)
        assert len(data[0]["accessRights"]) == 2
        assert data[0]["accessRights"] == {
            f"{logged_user['primary_gid']}": {
                "read": True,
                "write": True,
                "delete": True,
            },
            f"{new_user['primary_gid']}": {
                "read": True,
                "write": False,
                "delete": False,
            },
        }

        # Update the project permissions of the added user
        url = client.app.router["replace_project_group"].url_for(
            project_id=f"{user_project['uuid']}",
            group_id=f"{new_user['primary_gid']}",
        )
        resp = await client.put(
            f"{url}", json={"read": True, "write": True, "delete": False}
        )
        data, _ = await assert_status(resp, status.HTTP_200_OK)
        assert data["gid"] == new_user["primary_gid"]
        assert data["read"] is True
        assert data["write"] is True
        assert data["delete"] is False

        # List the project groups
        url = client.app.router["list_project_groups"].url_for(
            project_id=f"{user_project['uuid']}"
        )
        resp = await client.get(f"{url}")
        data, _ = await assert_status(resp, status.HTTP_200_OK)
        assert len(data) == 2
        assert data[1]["gid"] == new_user["primary_gid"]
        assert data[1]["read"] is True
        assert data[1]["write"] is True
        assert data[1]["delete"] is False

        # Get the project endpoint and check the permissions
        url = client.app.router["get_project"].url_for(
            project_id=f"{user_project['uuid']}",
        )
        resp = await client.get(f"{url}")
        data, _ = await assert_status(resp, status.HTTP_200_OK)
        assert len(data["accessRights"]) == 2
        assert data["accessRights"] == {
            f"{logged_user['primary_gid']}": {
                "read": True,
                "write": True,
                "delete": True,
            },
            f"{new_user['primary_gid']}": {
                "read": True,
                "write": True,
                "delete": False,
            },
        }

        # List project endpoint and check permissions
        url = client.app.router["list_projects"].url_for()
        resp = await client.get(f"{url}")
        data, _ = await assert_status(resp, status.HTTP_200_OK)
        assert len(data[0]["accessRights"]) == 2
        assert data[0]["accessRights"] == {
            f"{logged_user['primary_gid']}": {
                "read": True,
                "write": True,
                "delete": True,
            },
            f"{new_user['primary_gid']}": {
                "read": True,
                "write": True,
                "delete": False,
            },
        }

        # Delete the project group
        url = client.app.router["delete_project_group"].url_for(
            project_id=f"{user_project['uuid']}",
            group_id=f"{new_user['primary_gid']}",
        )
        resp = await client.delete(f"{url}")
        await assert_status(resp, status.HTTP_204_NO_CONTENT)

        # List the project groups
        url = client.app.router["list_project_groups"].url_for(
            project_id=f"{user_project['uuid']}"
        )
        resp = await client.get(f"{url}")
        data, _ = await assert_status(resp, status.HTTP_200_OK)
        assert len(data) == 1
        assert data[0]["gid"] == logged_user["primary_gid"]

        # List the projects endpoint and check the permissions
        url = client.app.router["get_project"].url_for(
            project_id=f"{user_project['uuid']}",
        )
        resp = await client.get(f"{url}")
        data, _ = await assert_status(resp, status.HTTP_200_OK)
        assert len(data["accessRights"]) == 1
        assert data["accessRights"] == {
            f"{logged_user['primary_gid']}": {
                "read": True,
                "write": True,
                "delete": True,
            },
        }

        # List project endpoint and check permissions
        url = client.app.router["list_projects"].url_for()
        resp = await client.get(f"{url}")
        data, _ = await assert_status(resp, status.HTTP_200_OK)
        assert len(data[0]["accessRights"]) == 1
        assert data[0]["accessRights"] == {
            f"{logged_user['primary_gid']}": {
                "read": True,
                "write": True,
                "delete": True,
            },
        }


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_share_project(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
):
    assert client.app

    # Share the project with a fake email
    url = client.app.router["share_project"].url_for(
        project_id=f"{user_project['uuid']}"
    )
    resp = await client.post(
        f"{url}",
        json={
            "shareeEmail": "sharee@email.com",
            "sharerMessage": "hi there, this is the project we talked about",
            "read": True,
            "write": False,
            "delete": False,
        },
    )
    data, error = await assert_status(resp, status.HTTP_202_ACCEPTED)
    shared = ProjectShareAccepted.model_validate(data)
    assert shared.sharee_email == "sharee@email.com"
    assert shared.confirmation_link
    assert not error

    # Verify that only logged_user["primary_gid"] has access to the project
    url = client.app.router["list_project_groups"].url_for(
        project_id=f"{user_project['uuid']}"
    )
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)
    assert len(data) == 1
    assert data[0]["gid"] == logged_user["primary_gid"]
    assert data[0]["read"] is True
    assert data[0]["write"] is True
    assert data[0]["delete"] is True

    # check an invalid
    url = client.app.router["share_project"].url_for(
        project_id=f"{user_project['uuid']}"
    )
    resp = await client.post(
        f"{url}",
        json={
            "shareeEmail": "sharee@email.com",
            # invalid access rights combination
            "read": True,
            "write": False,
            "delete": True,
        },
    )
    await assert_status(resp, status.HTTP_422_UNPROCESSABLE_ENTITY)


@pytest.mark.parametrize(
    "user_role,expected_status",
    [
        (UserRole.ANONYMOUS, status.HTTP_401_UNAUTHORIZED),
        (UserRole.GUEST, status.HTTP_403_FORBIDDEN),
        (UserRole.USER, status.HTTP_202_ACCEPTED),
        (UserRole.TESTER, status.HTTP_202_ACCEPTED),
        (UserRole.ADMIN, status.HTTP_202_ACCEPTED),
    ],
)
async def test_share_project_with_roles(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    user_role: UserRole,
    expected_status: HTTPStatus,
):
    assert client.app

    assert logged_user["role"] == user_role

    # Attempt to share the project
    url = client.app.router["share_project"].url_for(
        project_id=f"{user_project['uuid']}"
    )
    resp = await client.post(
        f"{url}",
        json={
            "shareeEmail": "sharee@email.com",
            "sharerMessage": "Sharing project with role test",
            "read": True,
            "write": False,
            "delete": False,
        },
    )
    await assert_status(resp, expected_status)
