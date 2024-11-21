# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import hashlib
from typing import TypedDict

import osparc
import pytest
from pytest_simcore.helpers.typing_public_api import RegisteredUserDict


@pytest.fixture(scope="module")
def users_api(api_client: osparc.ApiClient) -> osparc.UsersApi:
    return osparc.UsersApi(api_client)


class GroupDict(TypedDict):
    gid: str
    label: str
    description: str


class ProfileGroupsDict(TypedDict):
    me: GroupDict
    organizations: GroupDict
    all: GroupDict


class ProfileDict(TypedDict):
    first_name: str
    last_name: str
    email: str
    login: str
    role: osparc.UserRoleEnum
    groups: ProfileGroupsDict
    gravatar_id: str


@pytest.fixture
def expected_profile(registered_user: RegisteredUserDict) -> ProfileDict:
    first_name = registered_user["first_name"]
    email = registered_user["email"].lower()  # all emails are stored this way
    username = email.split("@")[0]

    return ProfileDict(
        **{  # noqa: PIE804
            "first_name": first_name,
            "last_name": registered_user["last_name"],
            "login": email,
            "role": osparc.UserRoleEnum.USER,
            "groups": {
                "all": {
                    "gid": "1",
                    "label": "Everyone",
                    "description": "all users",
                },
                "organizations": [
                    {
                        "gid": "2",
                        "label": "osparc",
                        "description": "osparc product group",
                    }
                ],
                "me": {
                    "gid": "3",
                    "label": username,
                    "description": "primary group",
                },
            },
            "gravatar_id": hashlib.md5(email.encode()).hexdigest(),  # nosec
        }
    )


def test_get_user(users_api: osparc.UsersApi, expected_profile: ProfileDict):
    user: osparc.Profile = users_api.get_my_profile()

    assert user.login == expected_profile["login"]
    # NOTE: cannot predict gid! assert user.to_dict() == expected_profile


def test_update_user(users_api: osparc.UsersApi):
    before: osparc.Profile = users_api.get_my_profile()
    assert before.first_name != "Richard"

    after: osparc.Profile = users_api.update_my_profile(
        osparc.ProfileUpdate(first_name="Richard")
    )
    assert after != before
    assert after.first_name == "Richard"
    assert after == users_api.get_my_profile()
