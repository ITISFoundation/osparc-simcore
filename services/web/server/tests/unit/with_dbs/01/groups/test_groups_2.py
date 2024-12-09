# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import operator
from collections.abc import Callable

import pytest
import sqlalchemy as sa
from aiohttp.test_utils import TestClient
from models_library.api_schemas_webserver.groups import GroupGet, MyGroupsGet
from pydantic import TypeAdapter
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.webserver_login import UserInfoDict
from pytest_simcore.helpers.webserver_parametrizations import (
    ExpectedResponse,
    standard_role_response,
)
from servicelib.aiohttp import status
from servicelib.aiohttp.application import create_safe_application
from simcore_postgres_database.models.users import UserRole
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver.application_settings import setup_settings
from simcore_service_webserver.db.plugin import setup_db
from simcore_service_webserver.groups.plugin import setup_groups
from simcore_service_webserver.login.plugin import setup_login
from simcore_service_webserver.rest.plugin import setup_rest
from simcore_service_webserver.security.plugin import setup_security
from simcore_service_webserver.session.plugin import setup_session
from simcore_service_webserver.users.plugin import setup_users


@pytest.fixture
def client(
    event_loop,
    aiohttp_client: Callable,
    app_environment: EnvVarsDict,
    postgres_db: sa.engine.Engine,
) -> TestClient:
    app = create_safe_application()

    setup_settings(app)
    setup_db(app)
    setup_session(app)
    setup_security(app)
    setup_rest(app)
    setup_login(app)
    setup_users(app)
    setup_groups(app)

    return event_loop.run_until_complete(aiohttp_client(app))


@pytest.mark.parametrize(*standard_role_response(), ids=str)
async def test_groups_access_rights(
    client: TestClient,
    logged_user: UserInfoDict,
    user_role: UserRole,
    expected: ExpectedResponse,
):
    assert client.app
    url = client.app.router["list_groups"].url_for()
    assert f"{url}" == f"/{API_VTAG}/groups"

    response = await client.get(f"{url}")
    await assert_status(
        response, expected.ok if user_role != UserRole.GUEST else status.HTTP_200_OK
    )


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_list_user_groups_and_try_modify_organizations(
    client: TestClient,
    user_role: UserRole,
    standard_groups_owner: UserInfoDict,
    logged_user: UserInfoDict,
    primary_group: dict[str, str],
    standard_groups: list[dict[str, str]],
    all_group: dict[str, str],
):
    assert client.app
    assert logged_user["id"] != standard_groups_owner["id"]
    assert logged_user["role"] == user_role.value

    # List all groups (organizations, primary, everyone and products) I belong to
    url = client.app.router["list_groups"].url_for()
    assert f"{url}" == f"/{API_VTAG}/groups"

    response = await client.get(f"{url}")
    data, error = await assert_status(response, status.HTTP_200_OK)

    my_groups = MyGroupsGet.model_validate(data)
    assert not error

    assert my_groups.me.model_dump() == primary_group
    assert my_groups.all.model_dump() == all_group

    assert my_groups.organizations
    assert len(my_groups.organizations) == len(standard_groups)

    by_gid = operator.itemgetter("gid")
    assert sorted(
        TypeAdapter(list[GroupGet]).dump_python(my_groups.organizations, mode="json"),
        key=by_gid,
    ) == sorted(standard_groups, key=by_gid)

    for group in standard_groups:
        # try to delete a group
        url = client.app.router["delete_group"].url_for(gid=f"{group['gid']}")
        response = await client.delete(f"{url}")
        await assert_status(response, status.HTTP_403_FORBIDDEN)

        # try to add some user in the group
        url = client.app.router["add_group_user"].url_for(gid=f"{group['gid']}")
        response = await client.post(f"{url}", json={"uid": logged_user["id"]})
        await assert_status(response, status.HTTP_403_FORBIDDEN)

        # try to modify the user in the group
        url = client.app.router["update_group_user"].url_for(
            gid=f"{group['gid']}", uid=f"{logged_user['id']}"
        )
        response = await client.patch(
            f"{url}",
            json={"accessRights": {"read": True, "write": True, "delete": True}},
        )
        await assert_status(response, status.HTTP_403_FORBIDDEN)

        # try to remove the user from the group
        url = client.app.router["delete_group_user"].url_for(
            gid=f"{group['gid']}", uid=f"{logged_user['id']}"
        )
        response = await client.delete(f"{url}")
        await assert_status(response, status.HTTP_403_FORBIDDEN)
