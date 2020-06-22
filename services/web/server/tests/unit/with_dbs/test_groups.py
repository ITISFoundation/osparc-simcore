# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


import random
from copy import deepcopy
from typing import Dict, List, Tuple

import pytest
from aiohttp import web

from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_login import LoggedUser, create_user
from servicelib.application import create_safe_application
from simcore_service_webserver.db import setup_db
from simcore_service_webserver.groups import setup_groups
from simcore_service_webserver.groups_api import (
    DEFAULT_GROUP_OWNER_ACCESS_RIGHTS,
    DEFAULT_GROUP_READ_ACCESS_RIGHTS,
)
from simcore_service_webserver.login import setup_login
from simcore_service_webserver.rest import setup_rest
from simcore_service_webserver.security import setup_security
from simcore_service_webserver.security_roles import UserRole
from simcore_service_webserver.session import setup_session
from simcore_service_webserver.users import setup_users

## BUG FIXES #######################################################
from simcore_service_webserver.utils import gravatar_hash

API_VERSION = "v0"


@pytest.fixture
def client(loop, aiohttp_client, app_cfg, postgres_service):
    cfg = deepcopy(app_cfg)

    port = cfg["main"]["port"]

    assert cfg["rest"]["version"] == API_VERSION

    cfg["db"]["init_tables"] = True  # inits postgres_service

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


@pytest.fixture
async def logged_user(client, role: UserRole):
    """ adds a user in db and logs in with client

    NOTE: role fixture is defined as a parametrization below
    """
    async with LoggedUser(
        client, {"role": role.name}, check_if_succeeds=role != UserRole.ANONYMOUS
    ) as user:
        yield user


# --------------------------------------------------------------------------
PREFIX = "/" + API_VERSION + "/groups"


def _assert_group(group: Dict[str, str]):
    properties = ["gid", "label", "description", "thumbnail", "access_rights"]
    assert all(x in group for x in properties)
    access_rights = group["access_rights"]
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
    assert "access_rights" in actual_user
    assert actual_user["access_rights"] == expected_access_rights
    assert "id" in actual_user
    assert actual_user["id"] == expected_user["id"]
    assert "gid" in actual_user


@pytest.mark.parametrize(
    "role,expected",
    [
        (UserRole.ANONYMOUS, web.HTTPUnauthorized),
        (UserRole.GUEST, web.HTTPForbidden),
        (UserRole.USER, web.HTTPOk),
        (UserRole.TESTER, web.HTTPOk),
    ],
)
async def test_list_groups(
    client,
    logged_user,
    role,
    expected,
    primary_group: Dict[str, str],
    standard_groups: List[Dict[str, str]],
    all_group: Dict[str, str],
):
    url = client.app.router["list_groups"].url_for()
    assert str(url) == f"{PREFIX}"

    resp = await client.get(url)
    data, error = await assert_status(resp, expected)

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


def _standard_role_response() -> Tuple[
    str, List[Tuple[UserRole, web.Response, web.Response, web.Response]]
]:
    return (
        "role,expected_ok, expected_created, expected_no_contents, expected_not_found",
        [
            (
                UserRole.ANONYMOUS,
                web.HTTPUnauthorized,
                web.HTTPUnauthorized,
                web.HTTPUnauthorized,
                web.HTTPUnauthorized,
            ),
            (
                UserRole.GUEST,
                web.HTTPForbidden,
                web.HTTPForbidden,
                web.HTTPForbidden,
                web.HTTPForbidden,
            ),
            (
                UserRole.USER,
                web.HTTPOk,
                web.HTTPCreated,
                web.HTTPNoContent,
                web.HTTPNotFound,
            ),
            (
                UserRole.TESTER,
                web.HTTPOk,
                web.HTTPCreated,
                web.HTTPNoContent,
                web.HTTPNotFound,
            ),
        ],
    )


@pytest.mark.parametrize(
    "role,expected",
    [
        (UserRole.ANONYMOUS, web.HTTPUnauthorized),
        (UserRole.GUEST, web.HTTPForbidden),
        (UserRole.USER, web.HTTPOk),
        (UserRole.TESTER, web.HTTPOk),
    ],
)
async def test_group_access_rights(
    client,
    logged_user,
    role,
    expected,
    primary_group: Dict[str, str],
    standard_groups: List[Dict[str, str]],
    all_group: Dict[str, str],
):
    url = client.app.router["list_groups"].url_for()
    assert str(url) == f"{PREFIX}"

    resp = await client.get(url)
    data, error = await assert_status(resp, expected)

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


@pytest.mark.parametrize(
    "role,expected,expected_read,expected_delete,expected_not_found",
    [
        (
            UserRole.ANONYMOUS,
            web.HTTPUnauthorized,
            web.HTTPUnauthorized,
            web.HTTPUnauthorized,
            web.HTTPUnauthorized,
        ),
        (
            UserRole.GUEST,
            web.HTTPForbidden,
            web.HTTPForbidden,
            web.HTTPForbidden,
            web.HTTPForbidden,
        ),
        (
            UserRole.USER,
            web.HTTPCreated,
            web.HTTPOk,
            web.HTTPNoContent,
            web.HTTPNotFound,
        ),
        (
            UserRole.TESTER,
            web.HTTPCreated,
            web.HTTPOk,
            web.HTTPNoContent,
            web.HTTPNotFound,
        ),
    ],
)
async def test_group_creation_workflow(
    client,
    logged_user,
    role,
    expected,
    expected_read,
    expected_delete,
    expected_not_found,
):
    url = client.app.router["create_group"].url_for()
    assert str(url) == f"{PREFIX}"

    new_group = {
        "gid": "4564",
        "label": "Black Sabbath",
        "description": "The founders of Rock'N'Roll",
        "thumbnail": "https://www.startpage.com/av/proxy-image?piurl=https%3A%2F%2Fencrypted-tbn0.gstatic.com%2Fimages%3Fq%3Dtbn%3AANd9GcS3pAUISv_wtYDL9Ih4JtUfAWyHj9PkYMlEBGHJsJB9QlTZuuaK%26s&sp=1591105967T00f0b7ff95c7b3bca035102fa1ead205ab29eb6cd95acedcedf6320e64634f0c",
    }

    resp = await client.post(url, json=new_group)
    data, error = await assert_status(resp, expected)

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
        assert assigned_group["access_rights"] == {
            "read": True,
            "write": True,
            "delete": True,
        }

    # get the groups and check we are part of this new group
    url = client.app.router["list_groups"].url_for()
    assert str(url) == f"{PREFIX}"

    resp = await client.get(url)
    data, error = await assert_status(resp, expected_read)
    if not error:
        assert len(data["organizations"]) == 1
        assert data["organizations"][0] == assigned_group

    # check getting one group
    url = client.app.router["get_group"].url_for(gid=str(assigned_group["gid"]))
    assert str(url) == f"{PREFIX}/{assigned_group['gid']}"
    resp = await client.get(url)
    data, error = await assert_status(resp, expected_read)
    if not error:
        assert data == assigned_group

    # modify the group
    modified_group = {"label": "Led Zeppelin"}
    url = client.app.router["update_group"].url_for(gid=str(assigned_group["gid"]))
    assert str(url) == f"{PREFIX}/{assigned_group['gid']}"
    resp = await client.patch(url, json=modified_group)
    data, error = await assert_status(resp, expected_read)
    if not error:
        assert data != assigned_group
        _assert_group(data)
        assigned_group.update(**modified_group)
        assert data == assigned_group
    # check getting the group returns the newly modified group
    url = client.app.router["get_group"].url_for(gid=str(assigned_group["gid"]))
    assert str(url) == f"{PREFIX}/{assigned_group['gid']}"
    resp = await client.get(url)
    data, error = await assert_status(resp, expected_read)
    if not error:
        _assert_group(data)
        assert data == assigned_group

    # delete the group
    url = client.app.router["delete_group"].url_for(gid=str(assigned_group["gid"]))
    assert str(url) == f"{PREFIX}/{assigned_group['gid']}"
    resp = await client.delete(url)
    data, error = await assert_status(resp, expected_delete)
    if not error:
        assert not data

    # check deleting the same group again fails
    url = client.app.router["delete_group"].url_for(gid=str(assigned_group["gid"]))
    assert str(url) == f"{PREFIX}/{assigned_group['gid']}"
    resp = await client.delete(url)
    data, error = await assert_status(resp, expected_not_found)

    # check getting the group fails
    url = client.app.router["get_group"].url_for(gid=str(assigned_group["gid"]))
    assert str(url) == f"{PREFIX}/{assigned_group['gid']}"
    resp = await client.get(url)
    data, error = await assert_status(resp, expected_not_found)


@pytest.mark.parametrize(
    "role, expected_created,expected,expected_not_found,expected_no_content",
    [
        (
            UserRole.ANONYMOUS,
            web.HTTPUnauthorized,
            web.HTTPUnauthorized,
            web.HTTPUnauthorized,
            web.HTTPUnauthorized,
        ),
        (
            UserRole.GUEST,
            web.HTTPForbidden,
            web.HTTPForbidden,
            web.HTTPForbidden,
            web.HTTPForbidden,
        ),
        (
            UserRole.USER,
            web.HTTPCreated,
            web.HTTPOk,
            web.HTTPNotFound,
            web.HTTPNoContent,
        ),
        (
            UserRole.TESTER,
            web.HTTPCreated,
            web.HTTPOk,
            web.HTTPNotFound,
            web.HTTPNoContent,
        ),
    ],
)
async def test_add_remove_users_from_group(
    client,
    logged_user,
    role,
    expected_created,
    expected,
    expected_not_found,
    expected_no_content,
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
    data, error = await assert_status(resp, expected_not_found)

    url = client.app.router["create_group"].url_for()
    assert str(url) == f"{PREFIX}"

    resp = await client.post(url, json=new_group)
    data, error = await assert_status(resp, expected_created)

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
        assert assigned_group["access_rights"] == {
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
    data, error = await assert_status(resp, expected)

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
        data, error = await assert_status(resp, expected_no_content)

        get_group_user_url = client.app.router["get_group_user"].url_for(
            gid=str(assigned_group["gid"]), uid=str(created_users_list[i]["id"])
        )
        assert (
            str(get_group_user_url)
            == f"{PREFIX}/{assigned_group['gid']}/users/{created_users_list[i]['id']}"
        )
        resp = await client.get(get_group_user_url)
        data, error = await assert_status(resp, expected)
        if not error:
            _assert__group_user(
                created_users_list[i], DEFAULT_GROUP_READ_ACCESS_RIGHTS, data
            )
    # check list is correct
    resp = await client.get(get_group_users_url)
    data, error = await assert_status(resp, expected)
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
            update_group_user_url, json={"access_rights": MANAGER_ACCESS_RIGHTS}
        )
        data, error = await assert_status(resp, expected)
        if not error:
            _assert__group_user(created_users_list[i], MANAGER_ACCESS_RIGHTS, data)
        # check it is there
        get_group_user_url = client.app.router["get_group_user"].url_for(
            gid=str(assigned_group["gid"]), uid=str(created_users_list[i]["id"])
        )
        resp = await client.get(get_group_user_url)
        data, error = await assert_status(resp, expected)
        if not error:
            _assert__group_user(created_users_list[i], MANAGER_ACCESS_RIGHTS, data)
        # remove the user from the group
        delete_group_user_url = client.app.router["delete_group_user"].url_for(
            gid=str(assigned_group["gid"]), uid=str(created_users_list[i]["id"])
        )
        resp = await client.delete(delete_group_user_url)
        data, error = await assert_status(resp, expected_no_content)
        # do it again to check it is not found anymore
        resp = await client.delete(delete_group_user_url)
        data, error = await assert_status(resp, expected_not_found)

        # check it is not there anymore
        get_group_user_url = client.app.router["get_group_user"].url_for(
            gid=str(assigned_group["gid"]), uid=str(created_users_list[i]["id"])
        )
        resp = await client.get(get_group_user_url)
        data, error = await assert_status(resp, expected_not_found)


@pytest.mark.parametrize(
    "role, expected_created,expected_ok,expected_not_found,expected_no_content",
    [
        (
            UserRole.ANONYMOUS,
            web.HTTPUnauthorized,
            web.HTTPUnauthorized,
            web.HTTPUnauthorized,
            web.HTTPUnauthorized,
        ),
        (
            UserRole.GUEST,
            web.HTTPForbidden,
            web.HTTPForbidden,
            web.HTTPForbidden,
            web.HTTPForbidden,
        ),
        (
            UserRole.USER,
            web.HTTPCreated,
            web.HTTPOk,
            web.HTTPNotFound,
            web.HTTPNoContent,
        ),
        (
            UserRole.TESTER,
            web.HTTPCreated,
            web.HTTPOk,
            web.HTTPNotFound,
            web.HTTPNoContent,
        ),
    ],
)
async def test_group_access_rights(
    client,
    logged_user,
    role,
    expected_created,
    expected_ok,
    expected_not_found,
    expected_no_content,
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
    data, error = await assert_status(resp, expected_created)
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
        data, error = await assert_status(resp, expected_no_content)
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
    data, error = await assert_status(resp, expected_ok)
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
    data, error = await assert_status(resp, expected_ok)
