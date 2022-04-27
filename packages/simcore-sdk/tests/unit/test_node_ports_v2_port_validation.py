# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=no-member
# pylint:disable=protected-access
# pylint:disable=too-many-arguments


import json
from copy import deepcopy
from typing import List
from unittest.mock import AsyncMock

import pytest
from pydantic import BaseModel, conint, schema_of
from pydantic.error_wrappers import ValidationError
from simcore_sdk.node_ports_v2.port import Port
from simcore_sdk.node_ports_v2.port_validation import validate_port_content


def test_validate_port_content():
    # TODO:
    #  unit = {"freq": "Hz", "distances": ["m", "mm"], "other": {"distances": "mm", "frequency": "Hz" }}
    #  unit = "MHz" <-- we start here
    #  unit = "MHz,mm"
    # is unit valid? compatible with x_unit?

    value, unit = validate_port_content(
        "port_1",
        value=3.0,
        unit="milli-meter",
        # expected
        content_schema={
            "title": "simple number",
            "type": "number",
            "x_unit": "cm",
        },
    )

    #  3.0 mm -> 0.3 cm
    # NOTE: there are roundoff errors in the unit conversion
    assert unit == "centimeter"
    assert abs(value - 0.3) < 1e-14


async def test_port_with_array(mocker):
    mocker.patch.object(Port, "_node_ports", new=AsyncMock())

    # arrays
    port_meta = {
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

    print(json.dumps(port_meta, indent=1))
    print(json.dumps(expected_value, indent=1))

    port = Port(key="input_w_array", **port_meta)

    await port.set_value(expected_value)
    assert await port.get_value() == expected_value


async def test_port_with_array_of_object(mocker):
    mocker.patch.object(Port, "_node_ports", new=AsyncMock())

    class A(BaseModel):
        i: conint(gt=3)
        b: bool = False
        s: str
        l: List[int]

    content_schema = schema_of(List[A], title="array[A]")

    port_meta = {
        "label": "array_",
        "description": "Some array of As",
        "type": "ref_contentSchema",
        "contentSchema": content_schema,
    }
    sample = [{"i": 5, "s": "x", "l": [1, 2]}, {"i": 6, "s": "y", "l": [2]}]
    expected_value = [A(**i).dict() for i in sample]

    print(json.dumps(port_meta, indent=1))
    print(json.dumps(expected_value, indent=1))

    # valid data and should assign defaults
    value = deepcopy(sample)
    p = Port(key="k", value=value, **port_meta)
    assert p.value == expected_value

    value = deepcopy(sample)
    value[0]["i"] = 0  # violates >3 condition

    with pytest.raises(ValidationError) as excinfo:
        Port(key="k", value=value, **port_meta)

    assert (
        "0 is less than or equal to the minimum of 3"
        in excinfo.value.errors()[0]["msg"]
    )


async def test_port_with_object(mocker):
    mocker.patch.object(Port, "_node_ports", new=AsyncMock())

    # objects
    port_meta = {
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

    print(json.dumps(port_meta, indent=1))
    print(json.dumps(expected_value, indent=1))

    # valid data
    p = Port(key="k", value={"i": 3, "b": True, "s": "foo"}, **port_meta)
    assert p.value == expected_value

    # assigns defaults
    p = Port(key="k", value={"b": True, "s": "foo"}, **port_meta)
    assert p.value == expected_value

    # invalid data
    with pytest.raises(ValidationError):
        Port(key="k", value={"b": True}, **port_meta)

    # inits with None
    port = Port(key="input_w_obj", **port_meta)
    await port.set_value(expected_value)
    assert await port.get_value() == expected_value

    with pytest.raises(ValidationError):
        await port.set_value({"b": True})


async def test_port_with_units_and_constraints(mocker):
    mocker.patch.object(Port, "_node_ports", new=AsyncMock())

    # objects
    port_meta = {
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

    # valid data
    p = Port(key="port-name-goes-here", value=3.14, **port_meta)
    assert p.value == expected_value

    # fails constraints
    with pytest.raises(ValidationError) as exc_info:
        Port(key="port-name-goes-here", value=-3.14, **port_meta)

    assert isinstance(exc_info.value, ValidationError)
    assert len(exc_info.value.errors()) == 1

    validation_error = exc_info.value.errors()[0]
    print(validation_error)

    assert validation_error["loc"] == ("value",)  # starts with value,!
    assert validation_error["type"] == "value_error.port_validation.port_schema"
    assert "-3.14 is less than the minimum of 0" in validation_error["msg"]

    # inits with None + set_value
    port = Port(key="port-name-goes-here", **port_meta)
    await port.set_value(expected_value)
    assert await port.get_value() == expected_value

    # set_value and fail
    with pytest.raises(ValidationError) as exc_info:
        await port.set_value(-3.14)

    assert exc_info.value.errors()[0] == validation_error
