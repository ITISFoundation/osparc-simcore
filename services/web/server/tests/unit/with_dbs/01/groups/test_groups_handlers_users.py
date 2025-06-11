# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from collections.abc import AsyncIterable, AsyncIterator
from contextlib import AsyncExitStack

import pytest
from aiohttp.test_utils import TestClient
from faker import Faker
from models_library.api_schemas_webserver.groups import GroupGet, GroupUserGet
from models_library.groups import AccessRightsDict, Group, StandardGroupCreate
from pydantic import TypeAdapter
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.webserver_login import LoggedUser, NewUser, UserInfoDict
from pytest_simcore.helpers.webserver_parametrizations import (
    ExpectedResponse,
    standard_role_response,
)
from servicelib.aiohttp import status
from servicelib.status_codes_utils import is_2xx_success
from simcore_postgres_database.models.users import UserRole
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver.groups._groups_repository import (
    _DEFAULT_GROUP_OWNER_ACCESS_RIGHTS,
    _DEFAULT_GROUP_READ_ACCESS_RIGHTS,
)
from simcore_service_webserver.groups._groups_service import (
    create_standard_group,
    delete_standard_group,
)
from simcore_service_webserver.groups.api import auto_add_user_to_groups
from simcore_service_webserver.security import security_web


def _assert_group(group: dict[str, str]):
    return GroupGet.model_validate(group)


def _assert__group_user(
    expected_user: UserInfoDict,
    expected_access_rights: AccessRightsDict,
    actual_user: dict,
    group_owner_id: int,
):
    user = GroupUserGet.model_validate(actual_user)

    assert user.id
    assert user.gid

    # identifiers
    assert actual_user["userName"] == expected_user["name"]
    assert "id" in actual_user
    assert int(user.id) == expected_user["id"]

    assert "gid" in actual_user
    assert int(user.gid) == expected_user.get("primary_gid")

    # private profile
    is_private = int(group_owner_id) != int(actual_user["id"])
    assert "first_name" in actual_user
    assert actual_user["first_name"] == (
        None if is_private else expected_user.get("first_name")
    )
    assert "last_name" in actual_user
    assert actual_user["last_name"] == (
        None if is_private else expected_user.get("last_name")
    )
    assert "login" in actual_user
    assert actual_user["login"] == (None if is_private else expected_user["email"])

    # access-rights
    assert "accessRights" in actual_user
    assert actual_user["accessRights"] == expected_access_rights


@pytest.mark.parametrize(*standard_role_response())
async def test_add_remove_users_from_group(
    client: TestClient,
    logged_user: UserInfoDict,
    user_role: UserRole,
    expected: ExpectedResponse,
    faker: Faker,
):
    assert client.app
    new_group = {
        "gid": "5",
        "label": "team awesom",
        "description": "awesomeness is just the summary",
        "thumbnail": "https://www.startpage.com/av/proxy-image?piurl=https%3A%2F%2Fencrypted-tbn0.gstatic.com%2Fimages%3Fq%3Dtbn%3AANd9GcSQMopBeN0pq2gg6iIZuLGYniFxUdzi7a2LeT1Xg0Lz84bl36Nlqw%26s&sp=1591110539Tbbb022a272bc117e58cca2f2399e83e6b5d4a2d0a7c283330057d7718ae305bd",
    }

    # check that our group does not exist
    url = client.app.router["get_all_group_users"].url_for(gid=new_group["gid"])
    assert f"{url}" == f"/{API_VTAG}/groups/{new_group['gid']}/users"
    resp = await client.get(f"{url}")
    data, error = await assert_status(resp, expected.not_found)

    # Create group
    url = client.app.router["create_group"].url_for()
    assert f"{url}" == f"/{API_VTAG}/groups"
    resp = await client.post(f"{url}", json=new_group)
    data, error = await assert_status(resp, expected.created)

    assigned_group = new_group
    if not error:
        assert isinstance(data, dict)
        assigned_group = data

        _assert_group(assigned_group)

        # we get a new gid and the rest keeps the same
        assert assigned_group["gid"] != new_group["gid"]

        props = ["label", "description", "thumbnail"]
        assert {assigned_group[p] for p in props} == {new_group[p] for p in props}

        # we get all rights on the group since we are the creator
        assert assigned_group["accessRights"] == _DEFAULT_GROUP_OWNER_ACCESS_RIGHTS

    group_id = assigned_group["gid"]

    # check that our user is in the group of users
    url = client.app.router["get_all_group_users"].url_for(gid=f"{group_id}")
    assert f"{url}" == f"/{API_VTAG}/groups/{group_id}/users"
    resp = await client.get(f"{url}")
    data, error = await assert_status(resp, expected.ok)

    if not error:
        list_of_users = data
        assert len(list_of_users) == 1
        the_owner = list_of_users[0]
        _assert__group_user(
            logged_user,
            _DEFAULT_GROUP_OWNER_ACCESS_RIGHTS,
            the_owner,
            group_owner_id=the_owner["id"],
        )

    # create a random number of users and put them in the group
    num_new_users = faker.random_int(1, 10)
    created_users_list = []
    async with AsyncExitStack() as users_stack:
        for i in range(num_new_users):

            is_private = i % 2 == 0
            created_users_list.append(
                await users_stack.enter_async_context(
                    NewUser(
                        app=client.app, user_data={"privacy_hide_email": is_private}
                    )
                )
            )
            created_users_list[i]["is_private"] = is_private
            user_id = created_users_list[i]["id"]
            user_email = created_users_list[i]["email"]

            # ADD
            url = client.app.router["add_group_user"].url_for(gid=f"{group_id}")
            assert f"{url}" == f"/{API_VTAG}/groups/{group_id}/users"
            if is_private:
                # only if privacy allows
                resp = await client.post(f"{url}", json={"email": user_email})
                data, error = await assert_status(resp, expected.not_found)

                # always allowed
                resp = await client.post(f"{url}", json={"uid": user_id})
                await assert_status(resp, expected.no_content)
            else:
                # both work
                resp = await client.post(f"{url}", json={"email": user_email})
                await assert_status(resp, expected.no_content)

            # GET
            url = client.app.router["get_group_user"].url_for(
                gid=f"{group_id}", uid=f"{user_id}"
            )
            assert f"{url}" == f"/{API_VTAG}/groups/{group_id}/users/{user_id}"
            resp = await client.get(f"{url}")
            data, error = await assert_status(resp, expected.ok)
            if not error:
                _assert__group_user(
                    created_users_list[i],
                    _DEFAULT_GROUP_READ_ACCESS_RIGHTS,
                    data,
                    group_owner_id=the_owner["id"] if is_private else user_id,
                )

        # LIST:  check list is correct
        url = client.app.router["get_all_group_users"].url_for(gid=f"{group_id}")
        resp = await client.get(f"{url}")
        data, error = await assert_status(resp, expected.ok)
        if not error:
            list_of_users = data

            # now we should have all the users in the group + the owner
            all_created_users = [*created_users_list, logged_user]

            assert len(list_of_users) == len(all_created_users)
            for user in list_of_users:
                expected_user: UserInfoDict = next(
                    u for u in all_created_users if int(u["id"]) == int(user["id"])
                )
                expected_access_rigths = (
                    _DEFAULT_GROUP_OWNER_ACCESS_RIGHTS
                    if int(user["id"]) == int(logged_user["id"])
                    else _DEFAULT_GROUP_READ_ACCESS_RIGHTS
                )

                _assert__group_user(
                    expected_user,
                    expected_access_rigths,
                    user,
                    group_owner_id=(
                        the_owner["id"]
                        if expected_user.get("is_private", False)
                        else user["id"]
                    ),
                )

        # PATCH the user and REMOVE them from the group
        MANAGER_ACCESS_RIGHTS: AccessRightsDict = {
            "read": True,
            "write": True,
            "delete": False,
        }
        for i in range(num_new_users):
            group_id = assigned_group["gid"]
            user_id = created_users_list[i]["id"]
            is_private = created_users_list[i].get("is_private", False)

            # PATCH access-rights
            url = client.app.router["update_group_user"].url_for(
                gid=f"{group_id}", uid=f"{user_id}"
            )
            resp = await client.patch(
                f"{url}", json={"accessRights": MANAGER_ACCESS_RIGHTS}
            )
            data, error = await assert_status(resp, expected.ok)
            if not error:
                _assert__group_user(
                    created_users_list[i],
                    MANAGER_ACCESS_RIGHTS,
                    data,
                    group_owner_id=the_owner["id"] if is_private else user_id,
                )

            # GET: check it is there
            url = client.app.router["get_group_user"].url_for(
                gid=f"{group_id}", uid=f"{user_id}"
            )
            resp = await client.get(f"{url}")
            data, error = await assert_status(resp, expected.ok)
            if not error:
                _assert__group_user(
                    created_users_list[i],
                    MANAGER_ACCESS_RIGHTS,
                    data,
                    group_owner_id=the_owner["id"] if is_private else user_id,
                )

            # REMOVE the user from the group
            url = client.app.router["delete_group_user"].url_for(
                gid=f"{group_id}", uid=f"{user_id}"
            )
            resp = await client.delete(f"{url}")
            data, error = await assert_status(resp, expected.no_content)

            # REMOVE: do it again to check it is not found anymore
            resp = await client.delete(f"{url}")
            data, error = await assert_status(resp, expected.not_found)

            # GET check it is not there anymore
            url = client.app.router["get_group_user"].url_for(
                gid=f"{group_id}", uid=f"{user_id}"
            )
            resp = await client.get(f"{url}")
            data, error = await assert_status(resp, expected.not_found)


@pytest.mark.parametrize(*standard_role_response())
async def test_group_access_rights(
    client: TestClient,
    logged_user: UserInfoDict,
    user_role: UserRole,
    expected: ExpectedResponse,
):
    assert client.app
    # Use-case:
    # 1. create a group
    url = client.app.router["create_group"].url_for()
    assert f"{url}" == f"/{API_VTAG}/groups"

    new_group = {
        "gid": "4564",
        "label": f"this is user {logged_user['id']} group",
        "description": f"user {logged_user['email']} is the owner of that one",
        "thumbnail": None,
    }

    resp = await client.post(f"{url}", json=new_group)
    data, error = await assert_status(resp, expected.created)
    if not data:
        # role cannot create a group so stop here
        return

    assigned_group = data
    group_id = assigned_group["gid"]

    async with AsyncExitStack() as users_stack:
        # 1. have 2 users
        users = [
            await users_stack.enter_async_context(NewUser(app=client.app))
            for _ in range(2)
        ]

        # 2. ADD the users to the group
        add_group_user_url = client.app.router["add_group_user"].url_for(
            gid=f"{group_id}"
        )
        assert f"{add_group_user_url}" == f"/{API_VTAG}/groups/{group_id}/users"
        for user in users:
            resp = await client.post(f"{add_group_user_url}", json={"uid": user["id"]})
            await assert_status(resp, expected.no_content)

        # 3. PATCH: user 1 shall be a manager
        patch_group_user_url = client.app.router["update_group_user"].url_for(
            gid=f"{group_id}", uid=f"{users[0]['id']}"
        )
        assert (
            f"{patch_group_user_url}"
            == f"/{API_VTAG}/groups/{group_id}/users/{users[0]['id']}"
        )
        params = {"accessRights": {"read": True, "write": True, "delete": False}}
        resp = await client.patch(f"{patch_group_user_url}", json=params)
        await assert_status(resp, expected.ok)

        # 4. PATCH user 2 shall be a member
        patch_group_user_url = client.app.router["update_group_user"].url_for(
            gid=f"{group_id}", uid=f"{users[1]['id']}"
        )
        assert (
            f"{patch_group_user_url}"
            == f"/{API_VTAG}/groups/{group_id}/users/{users[1]['id']}"
        )
        resp = await client.patch(
            f"{patch_group_user_url}",
            json={"accessRights": {"read": True, "write": False, "delete": False}},
        )
        await assert_status(resp, expected.ok)

        # let's LOGIN as user 1
        url = client.app.router["auth_login"].url_for()
        resp = await client.post(
            f"{url}",
            json={
                "email": users[0]["email"],
                "password": users[0]["raw_password"],
            },
        )
        await assert_status(resp, expected.ok)

        # check as a manager I can REMOVE user 2
        delete_group_user_url = client.app.router["delete_group_user"].url_for(
            gid=f"{group_id}", uid=f"{users[1]['id']}"
        )
        assert (
            f"{delete_group_user_url}"
            == f"/{API_VTAG}/groups/{group_id}/users/{users[1]['id']}"
        )
        resp = await client.delete(f"{delete_group_user_url}")
        await assert_status(resp, expected.no_content)

        # as a manager I can ADD user 2 again
        resp = await client.post(f"{add_group_user_url}", json={"uid": users[1]["id"]})
        await assert_status(resp, expected.no_content)

        # as a manager I cannot DELETE the group
        url = client.app.router["delete_group"].url_for(gid=f"{group_id}")
        resp = await client.delete(f"{url}")
        await assert_status(resp, status.HTTP_403_FORBIDDEN)

        # now log in as user 2
        # LOGIN
        url = client.app.router["auth_login"].url_for()
        resp = await client.post(
            f"{url}",
            json={
                "email": users[1]["email"],
                "password": users[1]["raw_password"],
            },
        )
        await assert_status(resp, expected.ok)

        # as a member I cannot REMOVE user 1
        delete_group_user_url = client.app.router["delete_group_user"].url_for(
            gid=f"{group_id}", uid=f"{users[0]['id']}"
        )
        assert (
            f"{delete_group_user_url}"
            == f"/{API_VTAG}/groups/{group_id}/users/{users[0]['id']}"
        )
        resp = await client.delete(f"{delete_group_user_url}")
        await assert_status(resp, status.HTTP_403_FORBIDDEN)

        # as a member I cannot ADD user 1
        resp = await client.post(f"{add_group_user_url}", json={"uid": users[0]["id"]})
        await assert_status(resp, status.HTTP_403_FORBIDDEN)

        # as a member I cannot DELETE the grouop
        url = client.app.router["delete_group"].url_for(gid=f"{group_id}")
        resp = await client.delete(f"{url}")
        await assert_status(resp, status.HTTP_403_FORBIDDEN)


@pytest.mark.parametrize(*standard_role_response())
async def test_add_user_gets_added_to_group(
    client: TestClient,
    standard_groups: list[dict[str, str]],
    user_role: UserRole,
    expected: ExpectedResponse,
):

    assert client.app
    async with AsyncExitStack() as users_stack:
        for email in (
            # SEE StandardGroupCreate.inclusion_rules in
            #  packages/pytest-simcore/src/pytest_simcore/simcore_webserver_groups_fixtures.py
            "good@sparc.io",
            "bad@bad.com",
            "bad@osparc.com",
            "good@black.com",
            "bad@blanco.com",
        ):
            user = await users_stack.enter_async_context(
                LoggedUser(
                    client,
                    user_data={
                        "role": user_role.name,
                        "email": email,
                        "privacy_hide_email": False,
                    },
                    check_if_succeeds=user_role != UserRole.ANONYMOUS,
                )
            )
            await auto_add_user_to_groups(client.app, user["id"])

            url = client.app.router["list_groups"].url_for()
            assert f"{url}" == f"/{API_VTAG}/groups"

            resp = await client.get(f"{url}")
            data, error = await assert_status(
                resp, status.HTTP_200_OK if user_role == UserRole.GUEST else expected.ok
            )
            if not error:
                assert len(data["organizations"]) == (0 if "bad" in email else 1)

    # NOTE: here same email are used for different users! Therefore sessions get mixed!
    await security_web.clean_auth_policy_cache(client.app)


@pytest.fixture
async def group_where_logged_user_is_the_owner(
    client: TestClient,
    logged_user: UserInfoDict,
) -> AsyncIterator[Group]:
    assert client.app
    group, _ = await create_standard_group(
        app=client.app,
        user_id=logged_user["id"],
        create=StandardGroupCreate.model_validate(
            {
                "name": f"this is user {logged_user['id']} group",
                "description": f"user {logged_user['email']} is the owner of that one",
                "thumbnail": None,
            }
        ),
    )

    yield group

    await delete_standard_group(
        client.app, user_id=logged_user["id"], group_id=group.gid
    )


@pytest.mark.acceptance_test(
    "Fixes 🐛 https://github.com/ITISFoundation/osparc-issues/issues/812"
)
@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_adding_user_to_group_with_upper_case_email(
    client: TestClient,
    user_role: UserRole,
    group_where_logged_user_is_the_owner: Group,
    faker: Faker,
):
    assert client.app
    url = client.app.router["add_group_user"].url_for(
        gid=f"{group_where_logged_user_is_the_owner.gid}"
    )
    # adding a user to group with the email in capital letters
    # Tests 🐛 https://github.com/ITISFoundation/osparc-issues/issues/812
    async with NewUser(
        app=client.app, user_data={"privacy_hide_email": False}
    ) as registered_user:
        assert registered_user["email"]  # <--- this email is lower case

        response = await client.post(
            f"{url}",
            json={
                # <--- email in upper case
                "email": registered_user["email"].upper()
            },
        )
        data, error = await assert_status(response, status.HTTP_204_NO_CONTENT)

        assert not data
        assert not error


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
