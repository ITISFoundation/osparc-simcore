from copy import deepcopy
from datetime import datetime
from pprint import pformat
from typing import Any

import pytest
from faker import Faker
from models_library.generics import Envelope
from models_library.utils.fastapi_encoders import jsonable_encoder
from pydantic import BaseModel
from simcore_postgres_database.models.users import UserRole
from simcore_service_webserver.users_models import ProfileGet, Token


@pytest.mark.parametrize(
    "model_cls",
    (
        ProfileGet,
        Token,
    ),
)
def test_user_models_examples(
    model_cls: type[BaseModel], model_cls_examples: dict[str, Any]
):
    for name, example in model_cls_examples.items():
        print(name, ":", pformat(example))
        model_instance = model_cls(**example)
        assert model_instance, f"Failed with {name}"

        #
        # TokenEnveloped
        # TokensArrayEnveloped
        # TokenIdEnveloped
        # ProfileEnveloped
        #

        model_enveloped = Envelope[model_cls].parse_data(
            model_instance.dict(by_alias=True)
        )
        model_array_enveloped = Envelope[list[model_cls]].parse_data(
            [
                model_instance.dict(by_alias=True),
                model_instance.dict(by_alias=True),
            ]
        )

        assert model_enveloped.error is None
        assert model_array_enveloped.error is None


def test_profile_get_expiration_date(faker: Faker):

    fake_expiration = datetime.utcnow()

    profile = ProfileGet(
        login=faker.email(), role=UserRole.ADMIN, expiration_date=fake_expiration
    )

    assert fake_expiration.date() == profile.expiration_date

    # TODO: encoding in body!? UTC !! ??
    body = jsonable_encoder(profile.dict(exclude_unset=True, by_alias=True))
    assert body["expirationDate"] == fake_expiration.date().isoformat()


@pytest.mark.parametrize("user_role", [u.name for u in UserRole])
def test_profile_get_role(user_role: str):
    data = deepcopy(ProfileGet.Config.schema_extra["example"])
    data["role"] = user_role
    m1 = ProfileGet(**data)

    data["role"] = UserRole(user_role)
    m2 = ProfileGet(**data)
    assert m1 == m2
