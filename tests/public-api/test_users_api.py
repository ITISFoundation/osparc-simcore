# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import hashlib
from typing import TypedDict

import pytest
from osparc import ApiClient, UsersApi
from osparc.models import Profile, ProfileUpdate, UserRoleEnum
from pytest_simcore.helpers.utils_public_api import RegisteredUserDict


@pytest.fixture(scope="module")
def users_api(api_client: ApiClient) -> UsersApi:
    return UsersApi(api_client)


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
    role: UserRoleEnum
    groups: ProfileGroupsDict
    gravatar_id: str


@pytest.fixture
def expected_profile(registered_user: RegisteredUserDict) -> ProfileDict:
    email = registered_user["email"]

    return ProfileDict(
        **{
            "first_name": registered_user["first_name"],
            "last_name": registered_user["last_name"],
            "login": email,
            "role": UserRoleEnum.USER,
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
                    "label": "John",
                    "description": "primary group",
                },
            },
            "gravatar_id": hashlib.md5(email.encode()).hexdigest(),  # nosec
        }
    )


def test_get_user(users_api: UsersApi, expected_profile: ProfileDict):
    user: Profile = users_api.get_my_profile()

    assert user.login == expected_profile["login"]
    assert user.to_dict() == expected_profile


def test_update_user(users_api: UsersApi):
    before: Profile = users_api.get_my_profile()
    assert before.first_name != "Richard"

    after: Profile = users_api.update_my_profile(ProfileUpdate(first_name="Richard"))
    assert after != before
    assert after.first_name == "Richard"
    assert after == users_api.get_my_profile()
