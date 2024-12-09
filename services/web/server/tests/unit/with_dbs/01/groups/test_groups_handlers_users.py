# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from collections.abc import AsyncIterator
from contextlib import AsyncExitStack

import pytest
from aiohttp.test_utils import TestClient
from faker import Faker
from models_library.api_schemas_webserver.groups import GroupGet
from models_library.groups import AccessRightsDict, Group
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.webserver_login import LoggedUser, NewUser, UserInfoDict
from pytest_simcore.helpers.webserver_parametrizations import (
    ExpectedResponse,
    standard_role_response,
)
from servicelib.aiohttp import status
from simcore_postgres_database.models.users import UserRole
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver.groups._groups_api import (
    create_organization,
    delete_organization,
)
from simcore_service_webserver.groups._groups_db import (
    _DEFAULT_GROUP_OWNER_ACCESS_RIGHTS,
    _DEFAULT_GROUP_READ_ACCESS_RIGHTS,
)
from simcore_service_webserver.groups.api import auto_add_user_to_groups
from simcore_service_webserver.security.api import clean_auth_policy_cache
from simcore_service_webserver.utils import gravatar_hash


def _assert_group(group: dict[str, str]):
    return GroupGet.model_validate(group)


def _assert__group_user(
    expected_user: UserInfoDict,
    expected_access_rights: AccessRightsDict,
    actual_user: dict,
):
    assert "first_name" in actual_user
    assert actual_user["first_name"] == expected_user.get("first_name")
    assert "last_name" in actual_user
    assert actual_user["last_name"] == expected_user.get("last_name")
    assert "login" in actual_user
    assert actual_user["login"] == expected_user["email"]
    assert "gravatar_id" in actual_user
    assert actual_user["gravatar_id"] == gravatar_hash(expected_user["email"])
    assert "accessRights" in actual_user
    assert actual_user["accessRights"] == expected_access_rights
    assert "id" in actual_user
    assert actual_user["id"] == expected_user["id"]
    assert "gid" in actual_user


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

    # check that our user is in the group of users
    get_group_users_url = client.app.router["get_all_group_users"].url_for(
        gid=f"{assigned_group['gid']}"
    )
    assert (
        f"{get_group_users_url}" == f"/{API_VTAG}/groups/{assigned_group['gid']}/users"
    )
    resp = await client.get(f"{get_group_users_url}")
    data, error = await assert_status(resp, expected.ok)

    if not error:
        list_of_users = data
        assert len(list_of_users) == 1
        the_owner = list_of_users[0]
        _assert__group_user(logged_user, _DEFAULT_GROUP_OWNER_ACCESS_RIGHTS, the_owner)

    # create a random number of users and put them in the group
    add_group_user_url = client.app.router["add_group_user"].url_for(
        gid=f"{assigned_group['gid']}"
    )
    assert (
        f"{add_group_user_url}" == f"/{API_VTAG}/groups/{assigned_group['gid']}/users"
    )
    num_new_users = faker.random_int(1, 10)
    created_users_list = []

    async with AsyncExitStack() as users_stack:
        for i in range(num_new_users):
            created_users_list.append(
                await users_stack.enter_async_context(NewUser(app=client.app))
            )

            # add the user once per email once per id to test both
            params = (
                {"uid": created_users_list[i]["id"]}
                if i % 2 == 0
                else {"email": created_users_list[i]["email"]}
            )
            resp = await client.post(f"{add_group_user_url}", json=params)
            data, error = await assert_status(resp, expected.no_content)

            get_group_user_url = client.app.router["get_group_user"].url_for(
                gid=f"{assigned_group['gid']}", uid=f"{created_users_list[i]['id']}"
            )
            assert (
                f"{get_group_user_url}"
                == f"/{API_VTAG}/groups/{assigned_group['gid']}/users/{created_users_list[i]['id']}"
            )
            resp = await client.get(f"{get_group_user_url}")
            data, error = await assert_status(resp, expected.ok)
            if not error:
                _assert__group_user(
                    created_users_list[i], _DEFAULT_GROUP_READ_ACCESS_RIGHTS, data
                )
        # check list is correct
        resp = await client.get(f"{get_group_users_url}")
        data, error = await assert_status(resp, expected.ok)
        if not error:
            list_of_users = data

            # now we should have all the users in the group + the owner
            all_created_users = [*created_users_list, logged_user]
            assert len(list_of_users) == len(all_created_users)
            for actual_user in list_of_users:

                expected_users_list = list(
                    filter(
                        lambda x, ac=actual_user: x["email"] == ac["login"],
                        all_created_users,
                    )
                )
                assert len(expected_users_list) == 1
                expected_user = expected_users_list[0]

                expected_access_rigths = _DEFAULT_GROUP_READ_ACCESS_RIGHTS
                if actual_user["login"] == logged_user["email"]:
                    expected_access_rigths = _DEFAULT_GROUP_OWNER_ACCESS_RIGHTS

                _assert__group_user(
                    expected_user,
                    expected_access_rigths,
                    actual_user,
                )
                all_created_users.remove(expected_users_list[0])

        # modify the user and remove them from the group
        MANAGER_ACCESS_RIGHTS: AccessRightsDict = {
            "read": True,
            "write": True,
            "delete": False,
        }
        for i in range(num_new_users):
            update_group_user_url = client.app.router["update_group_user"].url_for(
                gid=f"{assigned_group['gid']}", uid=f"{created_users_list[i]['id']}"
            )
            resp = await client.patch(
                f"{update_group_user_url}", json={"accessRights": MANAGER_ACCESS_RIGHTS}
            )
            data, error = await assert_status(resp, expected.ok)
            if not error:
                _assert__group_user(created_users_list[i], MANAGER_ACCESS_RIGHTS, data)
            # check it is there
            get_group_user_url = client.app.router["get_group_user"].url_for(
                gid=f"{assigned_group['gid']}", uid=f"{created_users_list[i]['id']}"
            )
            resp = await client.get(f"{get_group_user_url}")
            data, error = await assert_status(resp, expected.ok)
            if not error:
                _assert__group_user(created_users_list[i], MANAGER_ACCESS_RIGHTS, data)
            # remove the user from the group
            delete_group_user_url = client.app.router["delete_group_user"].url_for(
                gid=f"{assigned_group['gid']}", uid=f"{created_users_list[i]['id']}"
            )
            resp = await client.delete(f"{delete_group_user_url}")
            data, error = await assert_status(resp, expected.no_content)
            # do it again to check it is not found anymore
            resp = await client.delete(f"{delete_group_user_url}")
            data, error = await assert_status(resp, expected.not_found)

            # check it is not there anymore
            get_group_user_url = client.app.router["get_group_user"].url_for(
                gid=f"{assigned_group['gid']}", uid=f"{created_users_list[i]['id']}"
            )
            resp = await client.get(f"{get_group_user_url}")
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

    async with AsyncExitStack() as users_stack:
        # 1. have 2 users
        users = [
            await users_stack.enter_async_context(NewUser(app=client.app))
            for _ in range(2)
        ]

        # 2. add the users to the group
        add_group_user_url = client.app.router["add_group_user"].url_for(
            gid=f"{assigned_group['gid']}"
        )
        assert (
            f"{add_group_user_url}"
            == f"/{API_VTAG}/groups/{assigned_group['gid']}/users"
        )
        for i, user in enumerate(users):
            params = {"uid": user["id"]} if i % 2 == 0 else {"email": user["email"]}
            resp = await client.post(f"{add_group_user_url}", json=params)
            data, error = await assert_status(resp, expected.no_content)

        # 3. user 1 shall be a manager
        patch_group_user_url = client.app.router["update_group_user"].url_for(
            gid=f"{assigned_group['gid']}", uid=f"{users[0]['id']}"
        )
        assert (
            f"{patch_group_user_url}"
            == f"/{API_VTAG}/groups/{assigned_group['gid']}/users/{users[0]['id']}"
        )
        params = {"accessRights": {"read": True, "write": True, "delete": False}}
        resp = await client.patch(f"{patch_group_user_url}", json=params)
        data, error = await assert_status(resp, expected.ok)

        # 4. user 2 shall be a member
        patch_group_user_url = client.app.router["update_group_user"].url_for(
            gid=f"{assigned_group['gid']}", uid=f"{users[1]['id']}"
        )
        assert (
            f"{patch_group_user_url}"
            == f"/{API_VTAG}/groups/{assigned_group['gid']}/users/{users[1]['id']}"
        )
        params = {"accessRights": {"read": True, "write": False, "delete": False}}
        resp = await client.patch(f"{patch_group_user_url}", json=params)
        data, error = await assert_status(resp, expected.ok)

        # let's login as user 1
        # login
        url = client.app.router["auth_login"].url_for()
        resp = await client.post(
            f"{url}",
            json={
                "email": users[0]["email"],
                "password": users[0]["raw_password"],
            },
        )
        await assert_status(resp, expected.ok)

        # check as a manager I can remove user 2
        delete_group_user_url = client.app.router["delete_group_user"].url_for(
            gid=f"{assigned_group['gid']}", uid=f"{users[1]['id']}"
        )
        assert (
            f"{delete_group_user_url}"
            == f"/{API_VTAG}/groups/{assigned_group['gid']}/users/{users[1]['id']}"
        )
        resp = await client.delete(f"{delete_group_user_url}")
        data, error = await assert_status(resp, expected.no_content)

        # as a manager I can add user 2 again
        resp = await client.post(f"{add_group_user_url}", json={"uid": users[1]["id"]})
        data, error = await assert_status(resp, expected.no_content)

        # as a manager I cannot delete the group
        url = client.app.router["delete_group"].url_for(gid=f"{assigned_group['gid']}")
        resp = await client.delete(f"{url}")
        data, error = await assert_status(resp, status.HTTP_403_FORBIDDEN)

        # now log in as user 2
        # login
        url = client.app.router["auth_login"].url_for()
        resp = await client.post(
            f"{url}",
            json={
                "email": users[1]["email"],
                "password": users[1]["raw_password"],
            },
        )
        await assert_status(resp, expected.ok)

        # as a member I cannot remove user 1
        delete_group_user_url = client.app.router["delete_group_user"].url_for(
            gid=f"{assigned_group['gid']}", uid=f"{users[0]['id']}"
        )
        assert (
            f"{delete_group_user_url}"
            == f"/{API_VTAG}/groups/{assigned_group['gid']}/users/{users[0]['id']}"
        )
        resp = await client.delete(f"{delete_group_user_url}")
        data, error = await assert_status(resp, status.HTTP_403_FORBIDDEN)

        # as a member I cannot add user 1
        resp = await client.post(f"{add_group_user_url}", json={"uid": users[0]["id"]})
        data, error = await assert_status(resp, status.HTTP_403_FORBIDDEN)

        # as a member I cannot delete the grouop
        url = client.app.router["delete_group"].url_for(gid=f"{assigned_group['gid']}")
        resp = await client.delete(f"{url}")
        data, error = await assert_status(resp, status.HTTP_403_FORBIDDEN)


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
            "good@sparc.io",
            "bad@bad.com",
            "bad@osparc.com",
            "good@black.com",
            "bad@blanco.com",
        ):
            user = await users_stack.enter_async_context(
                LoggedUser(
                    client,
                    user_data={"role": user_role.name, "email": email},
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
    await clean_auth_policy_cache(client.app)


@pytest.fixture
async def group_where_logged_user_is_the_owner(
    client: TestClient,
    logged_user: UserInfoDict,
) -> AsyncIterator[Group]:
    assert client.app
    group, _ = await create_organization(
        app=client.app,
        user_id=logged_user["id"],
        new_group_values={
            "gid": "6543",
            "label": f"this is user {logged_user['id']} group",
            "description": f"user {logged_user['email']} is the owner of that one",
            "thumbnail": None,
        },
    )

    yield group

    await delete_organization(client.app, user_id=logged_user["id"], group_id=group.gid)


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
        app=client.app,
    ) as registered_user:
        assert registered_user["email"]  # <--- this email is lower case

        response = await client.post(
            f"{url}",
            json={
                "email": registered_user["email"].upper()
            },  # <--- email in upper case
        )
        data, error = await assert_status(response, status.HTTP_204_NO_CONTENT)

        assert not data
        assert not error
