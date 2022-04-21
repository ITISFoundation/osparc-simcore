# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=no-member
# pylint:disable=protected-access
# pylint:disable=too-many-arguments


import json
from copy import deepcopy
from typing import Any, Dict, List
from unittest.mock import AsyncMock

import jsonschema
import pytest
from pint import UnitRegistry
from pydantic import BaseModel, conint, schema_of
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


async def test_port_with_array_of_object(mocker):
    mocker.patch.object(Port, "_node_ports", new=AsyncMock())

    class A(BaseModel):
        i: conint(gt=3)  #
        b: bool = False
        s: str
        l: List[int]

    content_schema = schema_of(List[A], title="array[A]")

    port_info = {
        "label": "array_",
        "description": "Some array of As",
        "type": "ref_contentSchema",
        "contentSchema": content_schema,
    }
    sample = [{"i": 5, "s": "x", "l": [1, 2]}, {"i": 6, "s": "y", "l": [2]}]
    expected_value = [A(**i).dict() for i in sample]

    print(json.dumps(port_info, indent=1))
    print(json.dumps(expected_value, indent=1))

    # valid data and should assign defaults
    value = deepcopy(sample)
    p = Port(key="k", value=value, **port_info)
    assert p.value == expected_value

    value = deepcopy(sample)
    value[0]["i"] = 0  # violates >3 condition

    with pytest.raises(ValidationError) as excinfo:
        Port(key="k", value=value, **port_info)

    assert (
        "0 is less than or equal to the minimum of 3"
        in excinfo.value.errors()[0]["msg"]
    )


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


@pytest.fixture(scope="module")
def unit_registry():
    return UnitRegistry()


@pytest.mark.skip(reason="DEV")
def test_it(unit_registry: UnitRegistry):
    pass


async def test_port_with_units_and_constraints(mocker):
    mocker.patch.object(Port, "_node_ports", new=AsyncMock())

    # objects
    port_info = {
        "label": "Time",
        "description": "Positive time in usec",
        "type": "ref_contentSchema",
        "contentSchema": {
            "title": "Time",
            "minimum": 0,
            "x_unit": "micro-second",
            "type": "number",
        },
    }

    expected_value = 3.14

    print(json.dumps(port_info, indent=1))
    # print(json.dumps(expected_value, indent=1))

    # valid data
    p = Port(key="port-name-goes-here", value=3.14, **port_info)
    assert p.value == expected_value

    # fails constraints
    with pytest.raises(ValidationError) as exc_info:
        Port(key="port-name-goes-here", value=-3.14, **port_info)

    assert isinstance(exc_info.value, ValidationError)
    assert len(exc_info.value.errors()) == 1

    validation_error = exc_info.value.errors()[0]
    print(validation_error)

    assert validation_error["loc"] == ("value",)  # starts with value,!
    assert validation_error["msg"] == "value_error"
    assert (
        validation_error["msg"]
        == "-3.4 invalid against content_schema: -3.4 is less than the minimum of 0"
    )  # after ":" is friendly

    # TODO: convert errors in PortValidationError that includes name of the port and which item failed and why?

    # inits with None and tests set_value
    port = Port(key="port-name-goes-here", **port_info)
    await port.set_value(expected_value)
    assert await port.get_value() == expected_value

    with pytest.raises(ValidationError) as exc_info:
        await port.set_value(-3.14)

    assert exc_info.value.errors()[0] == validation_error
