from enum import Enum

import pytest
from models_library.utils.common_validators import (
    create_enums_pre_validator,
    empty_str_to_none_pre_validator,
    none_to_empty_str_pre_validator,
)
from pydantic import BaseModel, ValidationError, validator


def test_enums_pre_validator():
    class Enum1(Enum):
        RED = "RED"

    class Model(BaseModel):
        color: Enum1

    class ModelWithPreValidator(BaseModel):
        color: Enum1

        _from_equivalent_enums = validator("color", allow_reuse=True, pre=True)(
            create_enums_pre_validator(Enum1)
        )

    # with Enum1
    model = Model(color=Enum1.RED)
    assert ModelWithPreValidator(color=Enum1.RED) == model

    # with Enum2
    class Enum2(Enum):
        RED = "RED"

    with pytest.raises(ValidationError):
        Model(color=Enum2.RED)

    assert ModelWithPreValidator(color=Enum2.RED) == model


def test_empty_str_to_none_pre_validator():
    class Model(BaseModel):
        nullable_message: str | None

        _empty_is_none = validator("nullable_message", allow_reuse=True, pre=True)(
            empty_str_to_none_pre_validator
        )

    model = Model.parse_obj({"nullable_message": None})
    assert model == Model.parse_obj({"nullable_message": ""})


def test_none_to_empty_str_pre_validator():
    class Model(BaseModel):
        message: str

        _none_is_empty = validator("message", allow_reuse=True, pre=True)(
            none_to_empty_str_pre_validator
        )

    model = Model.parse_obj({"message": ""})
    assert model == Model.parse_obj({"message": None})
