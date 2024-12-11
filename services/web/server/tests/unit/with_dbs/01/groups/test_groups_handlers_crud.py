# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import operator
from typing import AsyncIterable

import pytest
from aiohttp.test_utils import TestClient
from models_library.api_schemas_webserver.groups import (
    GroupGet,
    GroupUserGet,
    MyGroupsGet,
)
from pydantic import TypeAdapter
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.webserver_login import NewUser, UserInfoDict
from pytest_simcore.helpers.webserver_parametrizations import (
    ExpectedResponse,
    standard_role_response,
)
from servicelib.aiohttp import status
from servicelib.status_codes_utils import is_2xx_success
from simcore_postgres_database.models.users import UserRole
from simcore_service_webserver._meta import API_VTAG


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

    url = client.app.router["create_group"].url_for()
    assert f"{url}" == f"/{API_VTAG}/groups"
    resp = await client.post(
        f"{url}",
        json={"label": "Black Sabbath", "description": "The founders of Rock'N'Roll"},
    )
    await assert_status(resp, expected.created)


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

    assert my_groups.me.model_dump(by_alias=True) == primary_group
    assert my_groups.all.model_dump(by_alias=True) == all_group

    assert my_groups.organizations
    assert len(my_groups.organizations) == len(standard_groups)

    by_gid = operator.itemgetter("gid")
    assert sorted(
        TypeAdapter(list[GroupGet]).dump_python(
            my_groups.organizations, mode="json", by_alias=True
        ),
        key=by_gid,
    ) == sorted(standard_groups, key=by_gid)

    for i, group in enumerate(standard_groups):
        # try to delete a group
        url = client.app.router["delete_group"].url_for(gid=f"{group['gid']}")
        response = await client.delete(f"{url}")
        await assert_status(response, status.HTTP_403_FORBIDDEN)

        # try to add some user in the group
        url = client.app.router["add_group_user"].url_for(gid=f"{group['gid']}")

        if i % 2 == 0:
            # by user-id
            params = {"uid": logged_user["id"]}
        else:
            # by user name
            params = {"userName": logged_user["name"]}

        response = await client.post(f"{url}", json=params)
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


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_group_creation_workflow(
    client: TestClient,
    user_role: UserRole,
    logged_user: UserInfoDict,
):
    assert client.app
    assert logged_user["id"] != 0
    assert logged_user["role"] == user_role.value

    url = client.app.router["create_group"].url_for()
    new_group_data = {
        "label": "Black Sabbath",
        "description": "The founders of Rock'N'Roll",
        "thumbnail": "https://www.startpage.com/av/proxy-image?piurl=https%3A%2F%2Fencrypted-tbn0.gstatic.com%2Fimages%3Fq%3Dtbn%3AANd9GcS3pAUISv_wtYDL9Ih4JtUfAWyHj9PkYMlEBGHJsJB9QlTZuuaK%26s&sp=1591105967T00f0b7ff95c7b3bca035102fa1ead205ab29eb6cd95acedcedf6320e64634f0c",
    }

    resp = await client.post(f"{url}", json=new_group_data)
    data, error = await assert_status(resp, status.HTTP_201_CREATED)

    assert not error
    group = GroupGet.model_validate(data)

    # we get a new gid and the rest keeps the same
    assert (
        group.model_dump(include={"label", "description", "thumbnail"}, mode="json")
        == new_group_data
    )

    # we get full ownership (i.e all rights) on the group since we are the creator
    assert group.access_rights.model_dump() == {
        "read": True,
        "write": True,
        "delete": True,
    }

    # get the groups and check we are part of this new group
    url = client.app.router["list_groups"].url_for()
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)

    my_groups = MyGroupsGet.model_validate(data)
    assert my_groups.organizations
    assert len(my_groups.organizations) == 1
    assert (
        my_groups.organizations[0].model_dump(include=set(new_group_data), mode="json")
        == new_group_data
    )

    # check getting one group
    url = client.app.router["get_group"].url_for(gid=f"{group.gid}")
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)

    got_group = GroupGet.model_validate(data)
    assert got_group == group

    # modify the group
    url = client.app.router["update_group"].url_for(gid=f"{group.gid}")
    resp = await client.patch(f"{url}", json={"label": "Led Zeppelin"})
    data, _ = await assert_status(resp, status.HTTP_200_OK)

    updated_group = GroupGet.model_validate(data)
    assert updated_group.model_dump(exclude={"label"}) == got_group.model_dump(
        exclude={"label"}
    )
    assert updated_group.label == "Led Zeppelin"

    # check getting the group returns the newly modified group
    url = client.app.router["get_group"].url_for(gid=f"{updated_group.gid}")
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)

    got_group = GroupGet.model_validate(data)
    assert got_group == updated_group

    # delete the group
    url = client.app.router["delete_group"].url_for(gid=f"{updated_group.gid}")
    resp = await client.delete(f"{url}")
    await assert_status(resp, status.HTTP_204_NO_CONTENT)

    # check deleting the same group again fails
    url = client.app.router["delete_group"].url_for(gid=f"{updated_group.gid}")
    resp = await client.delete(f"{url}")
    _, error = await assert_status(resp, status.HTTP_404_NOT_FOUND)

    assert f"{group.gid}" in error["message"]

    # check getting the group fails
    url = client.app.router["get_group"].url_for(gid=f"{updated_group.gid}")
    resp = await client.get(f"{url}")
    _, error = await assert_status(resp, status.HTTP_404_NOT_FOUND)

    assert f"{group.gid}" in error["message"]


@pytest.fixture
async def other_user(
    client: TestClient, logged_user: UserInfoDict, is_private_user: bool
) -> AsyncIterable[UserInfoDict]:
    # new user different from logged_user
    async with NewUser(
        {
            "name": f"other_than_{logged_user['name']}",
            "role": "USER",
            "privacy_hide_email": is_private_user,
        },
        client.app,
    ) as user:
        yield user


@pytest.mark.acceptance_test(
    "https://github.com/ITISFoundation/osparc-simcore/pull/6917"
)
@pytest.mark.parametrize("user_role", [UserRole.USER])
@pytest.mark.parametrize("is_private_user", [True, False])
@pytest.mark.parametrize("add_user_by", ["user_email", "user_id", "user_name"])
async def test_create_organization_and_add_users(
    client: TestClient,
    user_role: UserRole,
    logged_user: UserInfoDict,
    other_user: UserInfoDict,
    is_private_user: bool,
    add_user_by: str,
):
    assert client.app
    assert logged_user["id"] != 0
    assert logged_user["role"] == user_role.value

    # CREATE GROUP
    url = client.app.router["create_group"].url_for()
    resp = await client.post(
        f"{url}",
        json={
            "label": "Amies sans-frontiers",
            "description": "A desperate attempt to make some friends",
        },
    )
    data, error = await assert_status(resp, status.HTTP_201_CREATED)

    assert not error
    group = GroupGet.model_validate(data)

    # i have another user
    user_id = other_user["id"]
    user_name = other_user["name"]
    user_email = other_user["email"]

    assert user_id != logged_user["id"]
    assert user_name != logged_user["name"]
    assert user_email != logged_user["email"]

    # ADD new user to GROUP
    url = client.app.router["add_group_user"].url_for(gid=f"{group.gid}")

    expected_status = status.HTTP_204_NO_CONTENT
    match add_user_by:
        case "user_email":
            param = {"email": user_email}
            if is_private_user:
                expected_status = status.HTTP_404_NOT_FOUND
        case "user_id":
            param = {"uid": user_id}
        case "user_name":
            param = {"userName": user_name}
        case _:
            pytest.fail(reason=f"parameter {add_user_by} was not accounted for")

    response = await client.post(f"{url}", json=param)
    await assert_status(response, expected_status)

    # LIST USERS in GROUP
    url = client.app.router["get_all_group_users"].url_for(gid=f"{group.gid}")
    response = await client.get(f"{url}")
    data, _ = await assert_status(response, status.HTTP_200_OK)

    group_members = TypeAdapter(list[GroupUserGet]).validate_python(data)
    if is_2xx_success(expected_status):
        assert user_id in [
            u.id for u in group_members
        ], "failed to add other-user to the group!"

    # DELETE GROUP
    url = client.app.router["delete_group"].url_for(gid=f"{group.gid}")
    resp = await client.delete(f"{url}")
    await assert_status(resp, status.HTTP_204_NO_CONTENT)
