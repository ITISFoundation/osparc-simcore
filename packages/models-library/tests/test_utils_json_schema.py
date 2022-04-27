# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import pytest
from models_library.utils.json_schema import (
    InvalidJsonSchema,
    JsonSchemaValidationError,
    jsonschema_validate_data,
    jsonschema_validate_schema,
)


def test_json_validation_with_array():
    # with array
    schema = {
        "title": "list[number]",
        "type": "array",
        "items": {"type": "number"},
    }

    data = [1, 2, 3]
    jsonschema_validate_schema(schema)
    jsonschema_validate_data(data, schema)


def test_invalid_json_schema():
    with pytest.raises(InvalidJsonSchema):
        jsonschema_validate_schema({"Foo": ""})


def test_json_validation_with_object():

    # with object
    schema = {
        "title": "an object named A",
        "type": "object",
        "properties": {
            "i": {"title": "Int", "type": "integer", "default": 3},
            "b": {"title": "Bool", "type": "boolean"},
            "s": {"title": "Str", "type": "string"},
        },
        "required": ["b", "s"],
    }

    data = {"b": True}
    with pytest.raises(JsonSchemaValidationError):
        jsonschema_validate_data(data, schema)

    jsonschema_validate_schema(schema)
    with pytest.raises(JsonSchemaValidationError):
        jsonschema_validate_data(data, schema)

    data = {"b": True, "s": "foo"}
    jsonschema_validate_data(data, schema)

    assert data == {"b": True, "s": "foo"}
    assert jsonschema_validate_data(data, schema, return_with_default=True) == {
        "b": True,
        "s": "foo",
        "i": 3,
    }
    assert jsonschema_validate_data(data, schema, return_with_default=False) == {
        "b": True,
        "s": "foo",
    }
