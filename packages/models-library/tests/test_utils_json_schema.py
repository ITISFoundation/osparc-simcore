# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from collections import deque

import pytest
from faker import Faker
from models_library.utils.json_schema import (
    InvalidJsonSchema,
    JsonSchemaValidationError,
    any_ref_key,
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
    invalid_schema = {"type": "this_is_a_wrong_type"}
    with pytest.raises(InvalidJsonSchema) as err_info:
        jsonschema_validate_schema(invalid_schema)

    error = err_info.value
    assert isinstance(error, InvalidJsonSchema)
    assert error.message == "'this_is_a_wrong_type' is not valid under any of the given schemas"
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
    assert error.context  # [<ValidationError: "'this_is_a_wrong_type' is not one of ['array', 'boolean', 'integer', 'null', 'number', 'object', 'string']">, <ValidationError: "'this_is_a_wrong_type' is not of type 'array'">]
    assert error.cause is None
    assert error.validator == "anyOf"
    assert error.validator_value == error.schema["anyOf"]
    assert error.instance == "this_is_a_wrong_type"
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
    assert error.cause is None
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


def test_resolve_content_schema(faker: Faker):
    #
    # https://python-jsonschema.readthedocs.io/en/stable/_modules/jsonschema/validators/#RefResolver.in_scope
    #
    import jsonschema
    import jsonschema.validators

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=[2, 3, 4], schema={"maxItems": 2})

    schema_with_ref = {
        "title": "Complex_value",
        "$ref": "#/definitions/Complex",
        "definitions": {
            "Complex": {
                "title": "Complex",
                "type": "object",
                "properties": {
                    "real": {"title": "Real", "default": 0, "type": "number"},
                    "imag": {"title": "Imag", "default": 0, "type": "number"},
                },
            }
        },
    }

    assert any_ref_key(schema_with_ref)

    resolver = jsonschema.RefResolver.from_schema(schema_with_ref)
    assert resolver.resolution_scope == ""
    assert resolver.base_uri == ""

    ref, schema_resolved = resolver.resolve(schema_with_ref["$ref"])

    assert ref == "#/definitions/Complex"
    assert schema_resolved == {
        "title": "Complex",
        "type": "object",
        "properties": {
            "real": {"title": "Real", "default": 0, "type": "number"},
            "imag": {"title": "Imag", "default": 0, "type": "number"},
        },
    }

    assert not any_ref_key(schema_resolved)

    validator = jsonschema.validators.validator_for(schema_with_ref)
    validator.check_schema(schema_with_ref)

    instance = {"real": faker.pyfloat()}
    assert validator(schema_with_ref).is_valid(instance)
    assert validator(schema_resolved).is_valid(instance)
