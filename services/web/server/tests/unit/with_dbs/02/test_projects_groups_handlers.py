# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements


from http import HTTPStatus

import pytest
from aiohttp.test_utils import TestClient
from pytest_mock.plugin import MockerFixture
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.webserver_login import NewUser, UserInfoDict
from servicelib.aiohttp import status
from simcore_service_webserver.db.models import UserRole
from simcore_service_webserver.projects.models import ProjectDict


@pytest.fixture
def mock_catalog_api_get_services_for_user_in_product(mocker: MockerFixture):
    mocker.patch(
        "simcore_service_webserver.projects._crud_handlers.get_services_for_user_in_product",
        spec=True,
        return_value=[],
    )


@pytest.fixture
def mock_project_uses_available_services(mocker: MockerFixture):
    mocker.patch(
        "simcore_service_webserver.projects._crud_handlers.project_uses_available_services",
        spec=True,
        return_value=True,
    )


@pytest.fixture
def mock_catalog_api_get_services_for_user_in_product_2(mocker: MockerFixture):
    mocker.patch(
        "simcore_service_webserver.projects._crud_api_read.get_services_for_user_in_product",
        spec=True,
        return_value=[],
    )


@pytest.mark.acceptance_test(
    "Driving test for https://github.com/ITISFoundation/osparc-issues/issues/1547"
)
@pytest.mark.parametrize("user_role,expected", [(UserRole.USER, status.HTTP_200_OK)])
async def test_projects_groups_full_workflow(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    expected: HTTPStatus,
    mock_catalog_api_get_services_for_user_in_product,
    mock_project_uses_available_services,
    mock_catalog_api_get_services_for_user_in_product_2,
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
        assert data[1]["read"] == True
        assert data[1]["write"] == False
        assert data[1]["delete"] == False

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
        assert data["read"] == True
        assert data["write"] == True
        assert data["delete"] == False

        # List the project groups
        url = client.app.router["list_project_groups"].url_for(
            project_id=f"{user_project['uuid']}"
        )
        resp = await client.get(f"{url}")
        data, _ = await assert_status(resp, status.HTTP_200_OK)
        assert len(data) == 2
        assert data[1]["gid"] == new_user["primary_gid"]
        assert data[1]["read"] == True
        assert data[1]["write"] == True
        assert data[1]["delete"] == False

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
