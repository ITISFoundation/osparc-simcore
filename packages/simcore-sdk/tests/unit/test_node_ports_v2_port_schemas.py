# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=no-member
# pylint:disable=protected-access
# pylint:disable=too-many-arguments


import json
from typing import Any, Dict
from unittest.mock import AsyncMock

import jsonschema
import pytest
from pydantic.error_wrappers import ValidationError
from simcore_sdk.node_ports_v2.port import Port
from simcore_sdk.node_ports_v2.utils_schemas import (
    jsonschema_validate_data,
    jsonschema_validate_schema,
)

# HELPERS --------------------------------------------------------------------------------------


def get_model_config_example(model_cls, label) -> Dict[str, Any]:
    return next(
        v for v in model_cls.Config.schema_extra["examples"] if v["label"] == label
    )


# TESTS --------------------------------------------------------------------------------------
def test_json_validation_with_array():
    # with array
    schema = {
        "title": "list[number]",
        "type": "array",
        "items": {"type": "number"},
    }

    data = [1, 2, 3]
    jsonschema.validate(data, schema)

    jsonschema_validate_schema(schema)
    jsonschema_validate_data(data, schema)


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
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(data, schema)

    jsonschema_validate_schema(schema)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema_validate_data(data, schema)

    data = {"b": True, "s": "foo"}
    jsonschema.validate(data, schema)

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


async def test_port_with_array(mocker):
    mocker.patch.object(Port, "_node_ports", new=AsyncMock())

    # arrays
    port_info = {
        "label": "array_numbers",
        "description": "Some array of numbers",
        "type": "ref_contentSchema",
        "contentSchema": {
            "title": "list[number]",
            "type": "array",
            "items": {"type": "number"},
        },
    }
    expected_value = [1, 2, 3]

    print(json.dumps(port_info, indent=1))
    print(json.dumps(expected_value, indent=1))

    port = Port(key="input_w_array", **port_info)

    await port.set_value(expected_value)
    assert await port.get_value() == expected_value


async def test_port_with_object(mocker):
    mocker.patch.object(Port, "_node_ports", new=AsyncMock())

    # objects
    port_info = {
        "label": "my_object",
        "description": "Some object",
        "type": "ref_contentSchema",
        "contentSchema": {
            "title": "an object named A",
            "type": "object",
            "properties": {
                "i": {"title": "Int", "type": "integer", "default": 3},
                "b": {"title": "Bool", "type": "boolean"},
                "s": {"title": "Str", "type": "string"},
            },
            "required": ["b", "s"],
        },
    }

    expected_value = {"i": 3, "b": True, "s": "foo"}

    print(json.dumps(port_info, indent=1))
    print(json.dumps(expected_value, indent=1))

    # valid data
    p = Port(key="k", value={"i": 3, "b": True, "s": "foo"}, **port_info)
    assert p.value == expected_value

    # assigns defaults
    p = Port(key="k", value={"b": True, "s": "foo"}, **port_info)
    assert p.value == expected_value

    # invalid data
    with pytest.raises(ValidationError):
        Port(key="k", value={"b": True}, **port_info)

    # inits with None
    port = Port(key="input_w_obj", **port_info)
    await port.set_value(expected_value)
    assert await port.get_value() == expected_value

    # FIXME: PC-> SAN set_value does not validate??
    # with pytest.raises(ValidationError):
    #     await port.set_value(
    #         {
    #             "b": True
    #         }
    #     )
