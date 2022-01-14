# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


import random
from copy import deepcopy
from typing import Dict, List

import pytest
from _helpers import standard_role_response
from aiohttp import web
from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_login import LoggedUser, create_user, log_client_in
from servicelib.aiohttp.application import create_safe_application
from simcore_service_webserver.db import setup_db
from simcore_service_webserver.groups import setup_groups
from simcore_service_webserver.groups_api import (
    DEFAULT_GROUP_OWNER_ACCESS_RIGHTS,
    DEFAULT_GROUP_READ_ACCESS_RIGHTS,
    auto_add_user_to_groups,
)
from simcore_service_webserver.login.module_setup import setup_login
from simcore_service_webserver.rest import setup_rest
from simcore_service_webserver.security import setup_security
from simcore_service_webserver.security_roles import UserRole
from simcore_service_webserver.session import setup_session
from simcore_service_webserver.users import setup_users

## BUG FIXES #######################################################
from simcore_service_webserver.utils import gravatar_hash

API_VERSION = "v0"


@pytest.fixture
def client(loop, aiohttp_client, app_cfg, postgres_db):
    cfg = deepcopy(app_cfg)

    port = cfg["main"]["port"]

    assert cfg["rest"]["version"] == API_VERSION

    # fake config
    app = create_safe_application(cfg)

    setup_db(app)
    setup_session(app)
    setup_security(app)
    setup_rest(app)
    setup_login(app)
    setup_users(app)
    setup_groups(app)

    client = loop.run_until_complete(
        aiohttp_client(app, server_kwargs={"port": port, "host": "localhost"})
    )
    return client


# --------------------------------------------------------------------------
PREFIX = "/" + API_VERSION + "/groups"


def _assert_group(group: Dict[str, str]):
    properties = ["gid", "label", "description", "thumbnail", "accessRights"]
    assert all(x in group for x in properties)
    access_rights = group["accessRights"]
    access_rights_properties = ["read", "write", "delete"]
    assert all(x in access_rights for x in access_rights_properties)


def _assert__group_user(
    expected_user: Dict, expected_access_rights: Dict[str, bool], actual_user: Dict
):
    assert "first_name" in actual_user
    parts = expected_user["name"].split(".") + [""]
    assert actual_user["first_name"] == parts[0]
    assert "last_name" in actual_user
    assert actual_user["last_name"] == parts[1]
    assert "login" in actual_user
    assert actual_user["login"] == expected_user["email"]
    assert "gravatar_id" in actual_user
    assert actual_user["gravatar_id"] == gravatar_hash(expected_user["email"])
    assert "accessRights" in actual_user
    assert actual_user["accessRights"] == expected_access_rights
    assert "id" in actual_user
    assert actual_user["id"] == expected_user["id"]
    assert "gid" in actual_user


@pytest.mark.parametrize(*standard_role_response(), ids=str)
async def test_list_groups(
    client,
    logged_user,
    user_role,
    expected,
    primary_group: Dict[str, str],
    standard_groups: List[Dict[str, str]],
    all_group: Dict[str, str],
):
    url = client.app.router["list_groups"].url_for()
    assert str(url) == f"{PREFIX}"

    resp = await client.get(url)
    data, error = await assert_status(
        resp, expected.ok if user_role != UserRole.GUEST else web.HTTPOk
    )

    if not error:
        assert isinstance(data, dict)
        assert "me" in data
        _assert_group(data["me"])
        assert data["me"] == primary_group

        assert "organizations" in data
        assert isinstance(data["organizations"], list)
        for group in data["organizations"]:
            _assert_group(group)
        assert data["organizations"] == standard_groups
        assert "all" in data
        _assert_group(data["all"])
        assert data["all"] == all_group

        for group in standard_groups:
            # try to delete a group
            url = client.app.router["delete_group"].url_for(gid=str(group["gid"]))
            resp = await client.delete(url)
            data, error = await assert_status(resp, web.HTTPForbidden)
            # try to add some user in the group
            url = client.app.router["add_group_user"].url_for(gid=str(group["gid"]))
            resp = await client.post(url, json={"uid": logged_user["id"]})
            data, error = await assert_status(resp, web.HTTPForbidden)
            # try to modify the user in the group
            url = client.app.router["update_group_user"].url_for(
                gid=str(group["gid"]), uid=str(logged_user["id"])
            )
            resp = await client.patch(
                url,
                json={"access_rights": {"read": True, "write": True, "delete": True}},
            )
            data, error = await assert_status(resp, web.HTTPForbidden)
            # try to remove the user from the group
            url = client.app.router["delete_group_user"].url_for(
                gid=str(group["gid"]), uid=str(logged_user["id"])
            )
            resp = await client.delete(url)
            data, error = await assert_status(resp, web.HTTPForbidden)


@pytest.mark.parametrize(*standard_role_response())
async def test_group_creation_workflow(client, logged_user, user_role, expected):
    url = client.app.router["create_group"].url_for()
    assert str(url) == f"{PREFIX}"

    new_group = {
        "gid": "4564",
        "label": "Black Sabbath",
        "description": "The founders of Rock'N'Roll",
        "thumbnail": "https://www.startpage.com/av/proxy-image?piurl=https%3A%2F%2Fencrypted-tbn0.gstatic.com%2Fimages%3Fq%3Dtbn%3AANd9GcS3pAUISv_wtYDL9Ih4JtUfAWyHj9PkYMlEBGHJsJB9QlTZuuaK%26s&sp=1591105967T00f0b7ff95c7b3bca035102fa1ead205ab29eb6cd95acedcedf6320e64634f0c",
    }

    resp = await client.post(url, json=new_group)
    data, error = await assert_status(resp, expected.created)

    assigned_group = new_group
    if not error:
        assert isinstance(data, dict)
        assigned_group = data
        _assert_group(assigned_group)
        # we get a new gid and the rest keeps the same
        assert assigned_group["gid"] != new_group["gid"]
        for prop in ["label", "description", "thumbnail"]:
            assert assigned_group[prop] == new_group[prop]
        # we get all rights on the group since we are the creator
        assert assigned_group["accessRights"] == {
            "read": True,
            "write": True,
            "delete": True,
        }

    # get the groups and check we are part of this new group
    url = client.app.router["list_groups"].url_for()
    assert str(url) == f"{PREFIX}"

    resp = await client.get(url)
    data, error = await assert_status(
        resp, expected.ok if user_role != UserRole.GUEST else web.HTTPOk
    )
    if not error and user_role != UserRole.GUEST:
        assert len(data["organizations"]) == 1
        assert data["organizations"][0] == assigned_group

    # check getting one group
    url = client.app.router["get_group"].url_for(gid=str(assigned_group["gid"]))
    assert str(url) == f"{PREFIX}/{assigned_group['gid']}"
    resp = await client.get(url)
    data, error = await assert_status(
        resp, expected.ok if user_role != UserRole.GUEST else web.HTTPNotFound
    )
    if not error:
        assert data == assigned_group

    # modify the group
    modified_group = {"label": "Led Zeppelin"}
    url = client.app.router["update_group"].url_for(gid=str(assigned_group["gid"]))
    assert str(url) == f"{PREFIX}/{assigned_group['gid']}"
    resp = await client.patch(url, json=modified_group)
    data, error = await assert_status(resp, expected.ok)
    if not error:
        assert data != assigned_group
        _assert_group(data)
        assigned_group.update(**modified_group)
        assert data == assigned_group
    # check getting the group returns the newly modified group
    url = client.app.router["get_group"].url_for(gid=str(assigned_group["gid"]))
    assert str(url) == f"{PREFIX}/{assigned_group['gid']}"
    resp = await client.get(url)
    data, error = await assert_status(
        resp, expected.ok if user_role != UserRole.GUEST else web.HTTPNotFound
    )
    if not error:
        _assert_group(data)
        assert data == assigned_group

    # delete the group
    url = client.app.router["delete_group"].url_for(gid=str(assigned_group["gid"]))
    assert str(url) == f"{PREFIX}/{assigned_group['gid']}"
    resp = await client.delete(url)
    data, error = await assert_status(resp, expected.no_content)
    if not error:
        assert not data

    # check deleting the same group again fails
    url = client.app.router["delete_group"].url_for(gid=str(assigned_group["gid"]))
    assert str(url) == f"{PREFIX}/{assigned_group['gid']}"
    resp = await client.delete(url)
    data, error = await assert_status(resp, expected.not_found)

    # check getting the group fails
    url = client.app.router["get_group"].url_for(gid=str(assigned_group["gid"]))
    assert str(url) == f"{PREFIX}/{assigned_group['gid']}"
    resp = await client.get(url)
    data, error = await assert_status(
        resp, expected.not_found if user_role != UserRole.GUEST else web.HTTPNotFound
    )


@pytest.mark.parametrize(*standard_role_response())
async def test_add_remove_users_from_group(
    client,
    logged_user,
    user_role,
    expected,
):

    new_group = {
        "gid": "5",
        "label": "team awesom",
        "description": "awesomeness is just the summary",
        "thumbnail": "https://www.startpage.com/av/proxy-image?piurl=https%3A%2F%2Fencrypted-tbn0.gstatic.com%2Fimages%3Fq%3Dtbn%3AANd9GcSQMopBeN0pq2gg6iIZuLGYniFxUdzi7a2LeT1Xg0Lz84bl36Nlqw%26s&sp=1591110539Tbbb022a272bc117e58cca2f2399e83e6b5d4a2d0a7c283330057d7718ae305bd",
    }

    # check that our group does not exist
    url = client.app.router["get_group_users"].url_for(gid=new_group["gid"])
    assert str(url) == f"{PREFIX}/{new_group['gid']}/users"
    resp = await client.get(url)
    data, error = await assert_status(resp, expected.not_found)

    url = client.app.router["create_group"].url_for()
    assert str(url) == f"{PREFIX}"

    resp = await client.post(url, json=new_group)
    data, error = await assert_status(resp, expected.created)

    assigned_group = new_group
    if not error:
        assert isinstance(data, dict)
        assigned_group = data
        _assert_group(assigned_group)
        # we get a new gid and the rest keeps the same
        assert assigned_group["gid"] != new_group["gid"]
        for prop in ["label", "description", "thumbnail"]:
            assert assigned_group[prop] == new_group[prop]
        # we get all rights on the group since we are the creator
        assert assigned_group["accessRights"] == {
            "read": True,
            "write": True,
            "delete": True,
        }

    # check that our user is in the group of users
    get_group_users_url = client.app.router["get_group_users"].url_for(
        gid=str(assigned_group["gid"])
    )
    assert str(get_group_users_url) == f"{PREFIX}/{assigned_group['gid']}/users"
    resp = await client.get(get_group_users_url)
    data, error = await assert_status(resp, expected.ok)

    if not error:
        list_of_users = data
        assert len(list_of_users) == 1
        the_owner = list_of_users[0]
        _assert__group_user(logged_user, DEFAULT_GROUP_OWNER_ACCESS_RIGHTS, the_owner)

    # create a random number of users and put them in the group
    add_group_user_url = client.app.router["add_group_user"].url_for(
        gid=str(assigned_group["gid"])
    )
    assert str(add_group_user_url) == f"{PREFIX}/{assigned_group['gid']}/users"
    num_new_users = random.randint(1, 10)
    created_users_list = []
    for i in range(num_new_users):
        created_users_list.append(await create_user())

        # add the user once per email once per id to test both
        params = (
            {"uid": created_users_list[i]["id"]}
            if i % 2 == 0
            else {"email": created_users_list[i]["email"]}
        )
        resp = await client.post(add_group_user_url, json=params)
        data, error = await assert_status(resp, expected.no_content)

        get_group_user_url = client.app.router["get_group_user"].url_for(
            gid=str(assigned_group["gid"]), uid=str(created_users_list[i]["id"])
        )
        assert (
            str(get_group_user_url)
            == f"{PREFIX}/{assigned_group['gid']}/users/{created_users_list[i]['id']}"
        )
        resp = await client.get(get_group_user_url)
        data, error = await assert_status(resp, expected.ok)
        if not error:
            _assert__group_user(
                created_users_list[i], DEFAULT_GROUP_READ_ACCESS_RIGHTS, data
            )
    # check list is correct
    resp = await client.get(get_group_users_url)
    data, error = await assert_status(resp, expected.ok)
    if not error:
        list_of_users = data
        # now we should have all the users in the group + the owner
        all_created_users = created_users_list + [logged_user]
        assert len(list_of_users) == len(all_created_users)
        for actual_user in list_of_users:
            expected_users_list = list(
                filter(
                    lambda x, ac=actual_user: x["email"] == ac["login"],
                    all_created_users,
                )
            )
            assert len(expected_users_list) == 1
            _assert__group_user(
                expected_users_list[0],
                DEFAULT_GROUP_READ_ACCESS_RIGHTS
                if actual_user["login"] != logged_user["email"]
                else DEFAULT_GROUP_OWNER_ACCESS_RIGHTS,
                actual_user,
            )
            all_created_users.remove(expected_users_list[0])

    # modify the user and remove them from the group
    MANAGER_ACCESS_RIGHTS = {"read": True, "write": True, "delete": False}
    for i in range(num_new_users):
        update_group_user_url = client.app.router["update_group_user"].url_for(
            gid=str(assigned_group["gid"]), uid=str(created_users_list[i]["id"])
        )
        resp = await client.patch(
            update_group_user_url, json={"accessRights": MANAGER_ACCESS_RIGHTS}
        )
        data, error = await assert_status(resp, expected.ok)
        if not error:
            _assert__group_user(created_users_list[i], MANAGER_ACCESS_RIGHTS, data)
        # check it is there
        get_group_user_url = client.app.router["get_group_user"].url_for(
            gid=str(assigned_group["gid"]), uid=str(created_users_list[i]["id"])
        )
        resp = await client.get(get_group_user_url)
        data, error = await assert_status(resp, expected.ok)
        if not error:
            _assert__group_user(created_users_list[i], MANAGER_ACCESS_RIGHTS, data)
        # remove the user from the group
        delete_group_user_url = client.app.router["delete_group_user"].url_for(
            gid=str(assigned_group["gid"]), uid=str(created_users_list[i]["id"])
        )
        resp = await client.delete(delete_group_user_url)
        data, error = await assert_status(resp, expected.no_content)
        # do it again to check it is not found anymore
        resp = await client.delete(delete_group_user_url)
        data, error = await assert_status(resp, expected.not_found)

        # check it is not there anymore
        get_group_user_url = client.app.router["get_group_user"].url_for(
            gid=str(assigned_group["gid"]), uid=str(created_users_list[i]["id"])
        )
        resp = await client.get(get_group_user_url)
        data, error = await assert_status(resp, expected.not_found)


@pytest.mark.parametrize(*standard_role_response())
async def test_group_access_rights(
    client,
    logged_user,
    user_role,
    expected,
):
    # Use-case:
    # 1. create a group
    url = client.app.router["create_group"].url_for()
    assert str(url) == f"{PREFIX}"

    new_group = {
        "gid": "4564",
        "label": f"this is user {logged_user['id']} group",
        "description": f"user {logged_user['email']} is the owner of that one",
        "thumbnail": None,
    }

    resp = await client.post(url, json=new_group)
    data, error = await assert_status(resp, expected.created)
    if not data:
        # role cannot create a group so stop here
        return
    assigned_group = data

    # 1. have 2 users
    users = [await create_user() for i in range(2)]

    # 2. add the users to the group
    add_group_user_url = client.app.router["add_group_user"].url_for(
        gid=str(assigned_group["gid"])
    )
    assert str(add_group_user_url) == f"{PREFIX}/{assigned_group['gid']}/users"
    for i, user in enumerate(users):
        params = {"uid": user["id"]} if i % 2 == 0 else {"email": user["email"]}
        resp = await client.post(add_group_user_url, json=params)
        data, error = await assert_status(resp, expected.no_content)
    # 3. user 1 shall be a manager
    patch_group_user_url = client.app.router["update_group_user"].url_for(
        gid=str(assigned_group["gid"]), uid=str(users[0]["id"])
    )
    assert (
        str(patch_group_user_url)
        == f"{PREFIX}/{assigned_group['gid']}/users/{users[0]['id']}"
    )
    params = {"accessRights": {"read": True, "write": True, "delete": False}}
    resp = await client.patch(patch_group_user_url, json=params)
    data, error = await assert_status(resp, expected.ok)
    # 4. user 2 shall be a member
    patch_group_user_url = client.app.router["update_group_user"].url_for(
        gid=str(assigned_group["gid"]), uid=str(users[1]["id"])
    )
    assert (
        str(patch_group_user_url)
        == f"{PREFIX}/{assigned_group['gid']}/users/{users[1]['id']}"
    )
    params = {"accessRights": {"read": True, "write": False, "delete": False}}
    resp = await client.patch(patch_group_user_url, json=params)
    data, error = await assert_status(resp, expected.ok)

    # let's login as user 1
    # login
    url = client.app.router["auth_login"].url_for()
    resp = await client.post(
        url,
        json={
            "email": users[0]["email"],
            "password": users[0]["raw_password"],
        },
    )
    await assert_status(resp, expected.ok)
    # check as a manager I can remove user 2
    delete_group_user_url = client.app.router["delete_group_user"].url_for(
        gid=str(assigned_group["gid"]), uid=str(users[1]["id"])
    )
    assert (
        str(delete_group_user_url)
        == f"{PREFIX}/{assigned_group['gid']}/users/{users[1]['id']}"
    )
    resp = await client.delete(delete_group_user_url)
    data, error = await assert_status(resp, expected.no_content)
    # as a manager I can add user 2 again
    resp = await client.post(add_group_user_url, json={"uid": users[1]["id"]})
    data, error = await assert_status(resp, expected.no_content)
    # as a manager I cannot delete the group
    url = client.app.router["delete_group"].url_for(gid=str(assigned_group["gid"]))
    resp = await client.delete(url)
    data, error = await assert_status(resp, web.HTTPForbidden)

    # now log in as user 2
    # login
    url = client.app.router["auth_login"].url_for()
    resp = await client.post(
        url,
        json={
            "email": users[1]["email"],
            "password": users[1]["raw_password"],
        },
    )
    await assert_status(resp, expected.ok)
    # as a member I cannot remove user 1
    delete_group_user_url = client.app.router["delete_group_user"].url_for(
        gid=str(assigned_group["gid"]), uid=str(users[0]["id"])
    )
    assert (
        str(delete_group_user_url)
        == f"{PREFIX}/{assigned_group['gid']}/users/{users[0]['id']}"
    )
    resp = await client.delete(delete_group_user_url)
    data, error = await assert_status(resp, web.HTTPForbidden)
    # as a member I cannot add user 1
    resp = await client.post(add_group_user_url, json={"uid": users[0]["id"]})
    data, error = await assert_status(resp, web.HTTPForbidden)
    # as a member I cannot delete the grouop
    url = client.app.router["delete_group"].url_for(gid=str(assigned_group["gid"]))
    resp = await client.delete(url)
    data, error = await assert_status(resp, web.HTTPForbidden)


@pytest.mark.parametrize(*standard_role_response())
async def test_add_user_gets_added_to_group(
    client, standard_groups: List[Dict[str, str]], user_role, expected
):
    emails = [
        "good@sparc.io",
        "bad@bad.com",
        "bad@osparc.com",
        "good@black.com",
        "bad@blanco.com",
    ]
    for email in emails:
        user = await log_client_in(
            client,
            user_data={"role": user_role.name, "email": email},
            enable_check=user_role != UserRole.ANONYMOUS,
        )
        await auto_add_user_to_groups(client.app, user["id"])

        url = client.app.router["list_groups"].url_for()
        assert str(url) == f"{PREFIX}"

        resp = await client.get(url)
        data, error = await assert_status(
            resp, web.HTTPOk if user_role == UserRole.GUEST else expected.ok
        )
        if not error:
            assert len(data["organizations"]) == (0 if "bad" in email else 1)
