# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import hashlib

import osparc
import pytest
from osparc.models import Profile, UserRoleEnum


@pytest.fixture()
def users_api(api_client):
    return osparc.UsersApi(api_client)


@pytest.fixture
def expected_profile(registered_user):
    email = registered_user["email"]
    name, surname = email.split("@")[0].split(".")

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


def test_get_user(users_api, expected_profile):
    user: Profile = users_api.get_my_profile()

    # TODO: check all fields automatically
    assert user.login == expected_profile["login"]


def test_update_user(users_api):
    before: Profile = users_api.get_my_profile()
    assert before.first_name != "Foo"

    after: Profile = users_api.update_my_profile(first_name="Foo")
    assert after != before
    assert after.first_name == "Foo"
    assert after == users_api.get_my_profile()
