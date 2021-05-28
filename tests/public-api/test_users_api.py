# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import hashlib

import pytest
from osparc import UsersApi
from osparc.models import Profile, ProfileUpdate, UserRoleEnum


@pytest.fixture(scope="module")
def users_api(api_client):
    return UsersApi(api_client)


@pytest.fixture
def expected_profile(registered_user):
    email = registered_user["email"]
    name, _ = email.split("@")[0].split(".")

    return {
        "first_name": name.capitalize(),
        "last_name": name.capitalize(),
        "login": email,
        "role": UserRoleEnum.USER,
        "groups": {
            "me": {"gid": "123", "label": "maxy", "description": "primary group"},
            "organizations": [],
            "all": {"gid": "1", "label": "Everyone", "description": "all users"},
        },
        "gravatar_id": hashlib.md5(email.encode()).hexdigest(),  # nosec
    }


def test_get_user(users_api: UsersApi, expected_profile):
    user: Profile = users_api.get_my_profile()

    # TODO: check all fields automatically
    assert user.login == expected_profile["login"]


def test_update_user(users_api: UsersApi):
    before: Profile = users_api.get_my_profile()
    assert before.first_name != "Richard"

    after: Profile = users_api.update_my_profile(ProfileUpdate(first_name="Richard"))
    assert after != before
    assert after.first_name == "Richard"
    assert after == users_api.get_my_profile()
