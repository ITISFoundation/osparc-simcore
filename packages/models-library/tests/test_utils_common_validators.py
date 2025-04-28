from enum import Enum
from typing import Annotated

import pytest
from models_library.utils.common_validators import (
    create_enums_pre_validator,
    empty_str_to_none_pre_validator,
    none_to_empty_str_pre_validator,
    null_or_none_str_to_none_validator,
    trim_string_before,
)
from pydantic import BaseModel, StringConstraints, ValidationError, field_validator


def test_enums_pre_validator():
    class Enum1(Enum):
        RED = "RED"

    class Model(BaseModel):
        color: Enum1

    class ModelWithPreValidator(BaseModel):
        color: Enum1

        _from_equivalent_enums = field_validator("color", mode="before")(
            create_enums_pre_validator(Enum1)
        )

    # with Enum1
    model = Model(color=Enum1.RED)
    # See: https://docs.pydantic.dev/latest/migration/#changes-to-pydanticbasemodel
    assert ModelWithPreValidator(color=Enum1.RED).model_dump() == model.model_dump()

    # with Enum2
    class Enum2(Enum):
        RED = "RED"

    with pytest.raises(ValidationError):
        Model(color=Enum2.RED)

    # See: https://docs.pydantic.dev/latest/migration/#changes-to-pydanticbasemodel
    assert ModelWithPreValidator(color=Enum2.RED).model_dump() == model.model_dump()


def test_empty_str_to_none_pre_validator():
    class Model(BaseModel):
        nullable_message: str | None

        _empty_is_none = field_validator("nullable_message", mode="before")(
            empty_str_to_none_pre_validator
        )

    model = Model.model_validate({"nullable_message": None})
    assert model == Model.model_validate({"nullable_message": ""})


def test_none_to_empty_str_pre_validator():
    class Model(BaseModel):
        message: str

        _none_is_empty = field_validator("message", mode="before")(
            none_to_empty_str_pre_validator
        )

    model = Model.model_validate({"message": ""})
    assert model == Model.model_validate({"message": None})


def test_null_or_none_str_to_none_validator():
    class Model(BaseModel):
        message: str | None

        _null_or_none_str_to_none_validator = field_validator("message", mode="before")(
            null_or_none_str_to_none_validator
        )

    model = Model.model_validate({"message": "none"})
    assert model == Model.model_validate({"message": None})

    model = Model.model_validate({"message": "null"})
    assert model == Model.model_validate({"message": None})

    model = Model.model_validate({"message": "NoNe"})
    assert model == Model.model_validate({"message": None})

    model = Model.model_validate({"message": "NuLl"})
    assert model == Model.model_validate({"message": None})

    model = Model.model_validate({"message": None})
    assert model == Model.model_validate({"message": None})

    model = Model.model_validate({"message": ""})
    assert model == Model.model_validate({"message": ""})


def test_trim_string_before():
    max_length = 10

    class ModelWithTrim(BaseModel):
        text: Annotated[str, trim_string_before(max_length=max_length)]

    # Test with string shorter than max_length
    short_text = "Short"
    model = ModelWithTrim(text=short_text)
    assert model.text == short_text

    # Test with string equal to max_length
    exact_text = "1234567890"  # 10 characters
    model = ModelWithTrim(text=exact_text)
    assert model.text == exact_text

    # Test with string longer than max_length
    long_text = "This is a very long text that should be trimmed"
    model = ModelWithTrim(text=long_text)
    assert model.text == long_text[:max_length]
    assert len(model.text) == max_length

    # Test with non-string value (should be left unchanged)
    class ModelWithTrimOptional(BaseModel):
        text: Annotated[str | None, trim_string_before(max_length=max_length)]

    model = ModelWithTrimOptional(text=None)
    assert model.text is None


def test_trim_string_before_with_string_constraints():
    max_length = 10

    class ModelWithTrimAndConstraints(BaseModel):
        text: Annotated[
            str,
            trim_string_before(max_length=max_length),
            StringConstraints(max_length=max_length),
        ]

    # Check that the OpenAPI schema contains the string constraint
    schema = ModelWithTrimAndConstraints.model_json_schema()
    assert schema["properties"]["text"]["maxLength"] == max_length

    # Test with string longer than max_length
    # This should pass because trim_string_before runs first and trims the input
    # before StringConstraints validation happens
    long_text = "This is a very long text that should be trimmed"
    model = ModelWithTrimAndConstraints(text=long_text)
    assert model.text == long_text[:max_length]
    assert len(model.text) == max_length

    # Test with string exactly at max_length
    exact_text = "1234567890"  # 10 characters
    model = ModelWithTrimAndConstraints(text=exact_text)
    assert model.text == exact_text
