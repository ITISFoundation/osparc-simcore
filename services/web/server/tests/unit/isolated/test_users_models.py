from copy import deepcopy
from datetime import UTC, datetime
from pprint import pformat
from typing import Any

import pytest
from faker import Faker
from models_library.generics import Envelope
from models_library.utils.fastapi_encoders import jsonable_encoder
from pydantic import BaseModel
from servicelib.rest_constants import RESPONSE_MODEL_POLICY
from simcore_postgres_database.models.users import UserRole
from simcore_service_webserver.users.schemas import ProfileGet, ThirdPartyToken


@pytest.mark.parametrize(
    "model_cls",
    [ProfileGet, ThirdPartyToken],
)
def test_user_models_examples(
    model_cls: type[BaseModel], model_cls_examples: dict[str, Any]
):
    for name, example in model_cls_examples.items():
        print(name, ":", pformat(example))
        model_instance = model_cls(**example)
        assert model_instance, f"Failed with {name}"

        model_enveloped = Envelope[model_cls].from_data(
            model_instance.model_dump(by_alias=True)
        )
        model_array_enveloped = Envelope[list[model_cls]].from_data(
            [
                model_instance.model_dump(by_alias=True),
                model_instance.model_dump(by_alias=True),
            ]
        )

        assert model_enveloped.error is None
        assert model_array_enveloped.error is None


def test_profile_get_expiration_date(faker: Faker):
    fake_expiration = datetime.now(UTC)

    profile = ProfileGet(
        id=1,
        login=faker.email(),
        role=UserRole.ADMIN,
        expiration_date=fake_expiration.date(),
        preferences={},
    )

    assert fake_expiration.date() == profile.expiration_date

    body = jsonable_encoder(profile.model_dump(exclude_unset=True, by_alias=True))
    assert body["expirationDate"] == fake_expiration.date().isoformat()


def test_auto_compute_gravatar(faker: Faker):

    profile = ProfileGet(
        id=faker.pyint(),
        first_name=faker.first_name(),
        last_name=faker.last_name(),
        login=faker.email(),
        role="USER",
        preferences={},
    )

    envelope = Envelope[Any](data=profile)
    data = envelope.model_dump(**RESPONSE_MODEL_POLICY)["data"]

    assert data["gravatar_id"]
    assert data["id"] == profile.id
    assert data["first_name"] == profile.first_name
    assert data["last_name"] == profile.last_name
    assert data["login"] == profile.login
    assert data["role"] == profile.role
    assert data["preferences"] == profile.preferences


@pytest.mark.parametrize("user_role", [u.name for u in UserRole])
def test_profile_get_role(user_role: str):
    for example in ProfileGet.model_config["json_schema_extra"]["examples"]:
        data = deepcopy(example)
        data["role"] = user_role
        m1 = ProfileGet(**data)

        data["role"] = UserRole(user_role)
        m2 = ProfileGet(**data)
        assert m1 == m2


def test_parsing_output_of_get_user_profile():
    result_from_db_query_and_composition = {
        "id": 1,
        "login": "PtN5Ab0uv@guest-at-osparc.io",
        "first_name": "PtN5Ab0uv",
        "last_name": "",
        "role": "Guest",
        "gravatar_id": "9d5e02c75fcd4bce1c8861f219f7f8a5",
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

    profile = ProfileGet.model_validate(result_from_db_query_and_composition)
    assert "password" not in profile.model_dump(exclude_unset=True)
