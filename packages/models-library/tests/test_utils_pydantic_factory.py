# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from typing import Any

import pytest
from models_library.api_schemas_webserver._base import InputSchema, OutputSchema
from models_library.api_schemas_webserver.catalog import ServiceGet, ServiceUpdate
from models_library.utils.change_case import snake_to_camel
from models_library.utils.pydantic_factory import create_model_with_recursive_config
from pydantic import BaseModel, Field, ValidationError


class Address(BaseModel):
    street: str
    city: str
    postal_code: str  # <-- snake-case


class User(BaseModel):
    first_name: str  # <-- snake-case
    last_name: str  # <-- snake-case
    age: int
    address: Address = Field(..., description="this is an embedded BaseModel")


@pytest.fixture
def user_data_with_camelcase() -> dict[str, Any]:
    return {
        "firstName": "John",
        "lastName": "Doe",
        "age": 30,
        "address": {"street": "123 Main St", "city": "Anytown", "postalCode": "12345"},
    }


def test_config_is_not_recursive(user_data_with_camelcase: dict[str, Any]):
    # no config
    with pytest.raises(ValidationError, match="first_name"):
        User(**user_data_with_camelcase)

    # config only first model
    class NewUser(User):
        class Config:
            alias_generator = snake_to_camel
            allow_population_by_field_name = True

    with pytest.raises(ValidationError, match="postal_code"):
        NewUser(**user_data_with_camelcase)


def test_config_recursive(user_data_with_camelcase: dict[str, Any]):

    UserApi = create_model_with_recursive_config(
        User,
        {
            "alias_generator": snake_to_camel,
            "allow_population_by_field_name": True,
        },
        new_cls_name_suffix="Api",
    )

    # check name
    assert UserApi.__name__ == "UserApi"

    # check constructor
    user = UserApi(**user_data_with_camelcase)

    # check alias_generator
    print(user.json(by_alias=True, indent=2))
    assert user.dict(by_alias=True) == {
        "firstName": "John",
        "lastName": "Doe",
        "age": 30,
        "address": {"street": "123 Main St", "city": "Anytown", "postalCode": "12345"},
    }

    # check auto-generated OAS
    print(user.schema_json(indent=2))
    assert user.schema()["definitions"]["AddressApi"] == {  # by_alias=True by default
        "title": "AddressApi",
        "type": "object",
        "properties": {
            "street": {"title": "Street", "type": "string"},
            "city": {"title": "City", "type": "string"},
            "postalCode": {"title": "Postalcode", "type": "string"},  # <-- camel case
        },
        "required": ["street", "city", "postalCode"],
    }

    #  checks allow_population_by_field_name = True
    user2 = UserApi(**user.dict(by_alias=False))
    assert user2 == user

    # check preserves description
    assert (
        UserApi.__fields__["address"].field_info.description
        == User.__fields__["address"].field_info.description
    )


def test_create_models_for_web_api():
    def _to_dict(config_cls):
        return {k: v for k, v in config_cls.__dict__.items() if not k.startswith("_")}

    ServiceGetApi = create_model_with_recursive_config(
        ServiceGet,
        _to_dict(OutputSchema.Config),
        new_cls_name_suffix="Api",
    )

    print(ServiceGetApi.schema_json(indent=1))

    ServiceUpdateApi = create_model_with_recursive_config(
        ServiceUpdate,
        _to_dict(InputSchema.Config),
        new_cls_name_suffix="Api",
    )

    print(ServiceUpdateApi.schema_json(indent=1))
