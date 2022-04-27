# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from collections import deque

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
    invalid_schema = {"type": "invalid_type"}
    with pytest.raises(InvalidJsonSchema) as err_info:
        jsonschema_validate_schema(invalid_schema)

    error = err_info.value
    assert isinstance(error, InvalidJsonSchema)
    assert error.message == "'invalid_type' is not valid under any of the given schemas"
    assert error.path == deque(["type"])
    assert error.schema_path == deque(["allOf", 3, "properties", "type", "anyOf"])
    assert error.schema == {
        "anyOf": [
            {"$ref": "#/$defs/simpleTypes"},
            {
                "type": "array",
                "items": {"$ref": "#/$defs/simpleTypes"},
                "minItems": 1,
                "uniqueItems": True,
            },
        ]
    }
    assert (
        error.context
    )  # [<ValidationError: "'invalid_type' is not one of ['array', 'boolean', 'integer', 'null', 'number', 'object', 'string']">, <ValidationError: "'invalid_type' is not of type 'array'">]
    assert error.cause is None  #  self.__cause__ = cause
    assert error.validator == "anyOf"
    assert error.validator_value == error.schema["anyOf"]
    assert error.instance == "invalid_type"
    assert error.parent is None

    # raises the same with validate_data
    with pytest.raises(InvalidJsonSchema):
        jsonschema_validate_data({"x": 3}, invalid_schema)


@pytest.fixture
def valid_schema():
    return jsonschema_validate_schema(
        schema={
            "title": "an object named A",
            "type": "object",
            "properties": {
                "i": {"title": "Int", "type": "integer", "default": 3},
                "b": {"title": "Bool", "type": "boolean"},
                "s": {"title": "Str", "type": "string"},
            },
            "required": ["b", "s"],
        }
    )


def test_jsonschema_validate_data_error(valid_schema):
    schema = valid_schema
    data = {"b": True}
    with pytest.raises(JsonSchemaValidationError) as err_info:
        jsonschema_validate_data(data, schema)

    error = err_info.value
    assert isinstance(error, JsonSchemaValidationError)
    assert error.message == "'s' is a required property"
    assert error.path == deque([])
    assert error.schema_path == deque(["required"])
    assert error.schema == schema
    assert error.context == []
    assert error.cause is None  #  self.__cause__ = cause
    assert error.validator == "required"
    assert error.validator_value == schema["required"]
    assert error.instance == data
    assert error.parent is None


def test_jsonschema_validate_data_succeed(valid_schema):
    schema = valid_schema
    # Now with good data
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
