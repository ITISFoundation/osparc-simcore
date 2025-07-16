# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from datetime import UTC, datetime
from typing import Any

import pytest
from faker import Faker
from models_library.api_schemas_webserver.users import (
    MyProfileGet,
    MyProfilePatch,
    MyProfilePrivacyGet,
)
from models_library.generics import Envelope
from models_library.utils.fastapi_encoders import jsonable_encoder
from servicelib.rest_constants import RESPONSE_MODEL_POLICY
from simcore_postgres_database import utils_users
from simcore_service_webserver.users._models import ToUserUpdateDB


@pytest.fixture
def fake_profile_get(faker: Faker) -> MyProfileGet:
    fake_profile: dict[str, Any] = faker.simple_profile()
    first, last = fake_profile["name"].rsplit(maxsplit=1)

    return MyProfileGet(
        id=faker.pyint(),
        first_name=first,
        last_name=last,
        user_name=fake_profile["username"],
        login=fake_profile["mail"],
        role="USER",
        privacy=MyProfilePrivacyGet(
            hide_fullname=True, hide_email=True, hide_username=False
        ),
        preferences={},
    )


def test_profile_get_expiration_date(fake_profile_get: MyProfileGet):
    fake_expiration = datetime.now(UTC)

    profile = fake_profile_get.model_copy(
        update={"expiration_date": fake_expiration.date()}
    )

    assert fake_expiration.date() == profile.expiration_date

    body = jsonable_encoder(profile.model_dump(exclude_unset=True, by_alias=True))
    assert body["expirationDate"] == fake_expiration.date().isoformat()


def test_auto_compute_gravatar__deprecated(fake_profile_get: MyProfileGet):

    profile = fake_profile_get.model_copy()

    envelope = Envelope[Any](data=profile)
    data = envelope.model_dump(**RESPONSE_MODEL_POLICY)["data"]

    assert (
        "gravatar_id" not in data
    ), f"{dict(MyProfileGet.model_fields)['gravatar_id'].deprecated=}"
    assert data["id"] == profile.id
    assert data["first_name"] == profile.first_name
    assert data["last_name"] == profile.last_name
    assert data["login"] == profile.login
    assert data["role"] == profile.role
    assert data["preferences"] == profile.preferences


def test_parsing_output_of_get_user_profile():
    result_from_db_query_and_composition = {
        "id": 1,
        "login": "PtN5Ab0uv@guest-at-osparc.io",
        "userName": "PtN5Ab0uv",
        "first_name": "PtN5Ab0uv",
        "last_name": "",
        "role": "Guest",
        "gravatar_id": "9d5e02c75fcd4bce1c8861f219f7f8a5",
        "privacy": {"hide_email": True, "hide_fullname": False, "hide_username": False},
        "groups": {
            "me": {
                "gid": 2,
                "label": "PtN5Ab0uv",
                "description": "primary group",
                "thumbnail": None,
                "inclusionRules": {},
                "accessRights": {"read": True, "write": False, "delete": False},
            },
            "organizations": [],
            "all": {
                "gid": 1,
                "label": "Everyone",
                "description": "all users",
                "thumbnail": None,
                "inclusionRules": {},
                "accessRights": {"read": True, "write": False, "delete": False},
            },
        },
        "password": "secret",  # should be stripped out
        "preferences": {
            "confirmBackToDashboard": {"defaultValue": True, "value": True},
            "confirmDeleteStudy": {"defaultValue": True, "value": True},
            "confirmDeleteNode": {"defaultValue": True, "value": True},
            "confirmStopNode": {"defaultValue": True, "value": True},
            "snapNodeToGrid": {"defaultValue": True, "value": True},
            "autoConnectPorts": {"defaultValue": True, "value": True},
            "dontShowAnnouncements": {"defaultValue": [], "value": []},
            "services": {"defaultValue": {}, "value": {}},
            "themeName": {"defaultValue": None, "value": None},
            "lastVcsRefUI": {"defaultValue": None, "value": None},
            "preferredWalletId": {"defaultValue": None, "value": None},
        },
    }

    profile = MyProfileGet.model_validate(result_from_db_query_and_composition)
    assert "password" not in profile.model_dump(exclude_unset=True)


def test_mapping_update_models_from_rest_to_db():

    profile_update = MyProfilePatch.model_validate(
        # request payload
        {
            "first_name": "foo",
            "userName": "foo1234",
            "privacy": {"hideFullname": False, "hideUsername": True},
        }
    )

    # to db
    profile_update_db = ToUserUpdateDB.from_api(profile_update)

    # expected
    assert profile_update_db.to_db() == {
        "first_name": "foo",
        "name": "foo1234",
        "privacy_hide_fullname": False,
        "privacy_hide_username": True,
    }


def test_utils_user_generates_valid_myprofile_patch():
    username = utils_users._generate_username_from_email("xi@email.com")  # noqa: SLF001

    MyProfilePatch.model_validate({"userName": username})
    MyProfilePatch.model_validate(
        {"userName": utils_users.generate_alternative_username(username)}
    )
