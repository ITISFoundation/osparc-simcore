# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from copy import deepcopy

import pytest
from common_library.users_enums import UserRole
from models_library.api_schemas_webserver.users import (
    MyProfilePatch,
    MyProfileRestGet,
)
from pydantic import ValidationError


@pytest.mark.parametrize("user_role", [u.name for u in UserRole])
def test_profile_get_role(user_role: str):
    for example in MyProfileRestGet.model_json_schema()["examples"]:
        data = deepcopy(example)
        data["role"] = user_role
        m1 = MyProfileRestGet(**data)

        data["role"] = UserRole(user_role)
        m2 = MyProfileRestGet(**data)
        assert m1 == m2


def test_my_profile_patch_username_min_len():
    # minimum length username is 4
    with pytest.raises(ValidationError) as err_info:
        MyProfilePatch.model_validate({"userName": "abc"})

    assert err_info.value.error_count() == 1
    assert err_info.value.errors()[0]["type"] == "too_short"

    MyProfilePatch.model_validate({"userName": "abcd"})  # OK


def test_my_profile_patch_username_valid_characters():
    # Ensure valid characters (alphanumeric + . _ -)
    with pytest.raises(ValidationError, match="start with a letter") as err_info:
        MyProfilePatch.model_validate({"userName": "1234"})

    assert err_info.value.error_count() == 1
    assert err_info.value.errors()[0]["type"] == "value_error"

    MyProfilePatch.model_validate({"userName": "u1234"})  # OK


def test_my_profile_patch_username_special_characters():
    # Ensure no consecutive special characters
    with pytest.raises(
        ValidationError, match="consecutive special characters"
    ) as err_info:
        MyProfilePatch.model_validate({"userName": "u1__234"})

    assert err_info.value.error_count() == 1
    assert err_info.value.errors()[0]["type"] == "value_error"

    MyProfilePatch.model_validate({"userName": "u1_234"})  # OK

    # Ensure it doesn't end with a special character
    with pytest.raises(ValidationError, match="end with") as err_info:
        MyProfilePatch.model_validate({"userName": "u1234_"})

    assert err_info.value.error_count() == 1
    assert err_info.value.errors()[0]["type"] == "value_error"

    MyProfilePatch.model_validate({"userName": "u1_234"})  # OK


def test_my_profile_patch_username_reserved_words():
    # Check reserved words (example list; extend as needed)
    with pytest.raises(ValidationError, match="cannot be used") as err_info:
        MyProfilePatch.model_validate({"userName": "admin"})

    assert err_info.value.error_count() == 1
    assert err_info.value.errors()[0]["type"] == "value_error"

    MyProfilePatch.model_validate({"userName": "midas"})  # OK
