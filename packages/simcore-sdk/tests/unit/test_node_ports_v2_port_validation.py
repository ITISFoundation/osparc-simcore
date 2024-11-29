# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=no-member
# pylint:disable=protected-access
# pylint:disable=too-many-arguments


import json
import sys
from copy import deepcopy
from typing import Any
from unittest.mock import AsyncMock

import pytest
from pydantic import BaseModel, Field, TypeAdapter, ValidationError
from simcore_sdk.node_ports_v2.port import Port
from simcore_sdk.node_ports_v2.port_validation import (
    PortUnitError,
    validate_port_content,
)
from typing_extensions import Annotated


def _replace_value_in_dict(item: Any, original_schema: dict[str, Any]):
    #
    # Taken and adapted from https://github.com/samuelcolvin/pydantic/issues/889#issuecomment-850312496
    # Check as a more reliable solution https://github.com/gazpachoking/jsonref or see jsonschema.Resolver
    #
    if isinstance(item, list):
        return [_replace_value_in_dict(i, original_schema) for i in item]

    if isinstance(item, dict):
        if "$ref" in item.keys():
            # Limited to something like "$ref": "#/definitions/Engine"
            definitions = item["$ref"][2:].split("/")
            res = original_schema.copy()
            for definition in definitions:
                res = res[definition]
            return res
        return {
            key: _replace_value_in_dict(i, original_schema) for key, i in item.items()
        }
    return item


def _resolve_refs(schema: dict[str, Any]) -> dict[str, Any]:
    #  tmp solution until $ref  implemented

    if "$ref" in str(schema):
        # NOTE: this is a minimal solution that cannot cope e.g. with
        # the most generic $ref with might be URLs. For that we will be using
        # directly jsonschema python package's resolver in the near future.
        # In the meantime we can live with this
        return _replace_value_in_dict(deepcopy(schema), deepcopy(schema.copy()))
    return schema


def test_validate_port_content():
    #  unit = {"freq": "Hz", "distances": ["m", "mm"], "other": {"distances": "mm", "frequency": "Hz" }}
    #  unit = "MHz" <-- we start here
    #  unit = "MHz,mm"
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
    assert abs(value - 0.3) < 2 * sys.float_info.epsilon


def test_validate_port_content_fails():
    with pytest.raises(PortUnitError) as err_info:
        value, unit = validate_port_content(
            "port_1",
            value=3.0,
            unit="seconds",
            # expected
            content_schema={
                "title": "simple number",
                "type": "number",
                "x_unit": "cm",
            },
        )

    error_message = f"{err_info.value}"
    # "Invalid unit in port 'port_1': Cannot convert from 'second' ([time]) to 'centimeter' ([length])"
    assert "'port_1'" in error_message
    assert "'second'" in error_message
    assert "'centimeter'" in error_message


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
        i: Annotated[int, Field(gt=3)]
        b: bool = False
        s: str
        t: list[int]

    content_schema = _resolve_refs(
        {
            **TypeAdapter(list[A]).json_schema(),
            "title": "array[A]",
        }
    )

    port_meta = {
        "label": "array_",
        "description": "Some array of As",
        "type": "ref_contentSchema",
        "contentSchema": content_schema,
    }
    sample = [{"i": 5, "s": "x", "t": [1, 2]}, {"i": 6, "s": "y", "t": [2]}]
    expected_value = [A(**i).model_dump() for i in sample]

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

    assert len(excinfo.value.errors()) == 1

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
    assert validation_error["type"] == "value_error"
    assert "-3.14 is less than the minimum of 0" in validation_error["msg"]

    # inits with None + set_value
    port = Port(key="port-name-goes-here", **port_meta)
    await port.set_value(expected_value)
    assert await port.get_value() == expected_value

    # set_value and fail
    with pytest.raises(ValidationError) as exc_info:
        await port.set_value(-3.14)


def test_incident__port_validator_check_value():
    # SEE incident https://git.speag.com/oSparc/e2e-testing/-/issues/1)

    # schema in comp_tasks table
    comp_tasks_schema = {
        "inputs": {
            "input_1": {
                "displayOrder": 1.0,
                "label": "input_file",
                "description": "Input file for the solver. Generated with sim4life",
                "type": "data:*/*",
                "fileToKeyMap": {"input.h5": "input_1"},
                "defaultValue": "some_value(optional)",
            },
            "NGPU": {
                "displayOrder": 2.0,
                "label": "Number of GPUs",
                "description": "Defines the number of GPUs used for the computation (0 uses all)",
                "type": "integer",
                "defaultValue": 1,
            },
        },
        "outputs": {
            "output_1": {
                "displayOrder": 1.0,
                "label": "output_file",
                "description": "Output file from solver.",
                "type": "data:*/*",
                "fileToKeyMap": {"output.h5": "output_1"},
            },
            "output_2": {
                "displayOrder": 2.0,
                "label": "solver_logs",
                "description": "Log files from solver.",
                "type": "data:*/*",
                "fileToKeyMap": {"log.tgz": "output_2"},
            },
        },
    }

    # check outputs from project.workbench table
    inputs_value = {
        "outFile": {
            "store": 0,
            "dataset": "50339632-ee1d-11ec-a0c2-02420a0194e4",
            "path": "50339632-ee1d-11ec-a0c2-02420a0194e4/52ee5b71-be10-50dc-8bc6-2c14568c41ef/isolve_gpu_input.h5",
            "label": "isolve_gpu_input.h5",
        }
    }

    port_meta = comp_tasks_schema["inputs"]["input_1"]
    value = inputs_value["outFile"]

    Port(key="port-name-goes-here", value=value, **port_meta)

    # check outputs from comp_tasks table
    comp_tasks_outputs = {
        "output_1": {
            "store": "0",  # <---Here is the legacy issue
            "path": "50339632-ee1d-11ec-a0c2-02420a0194e4/23b1522f-225f-5a4c-9158-c4c19a70d4a8/output.h5",
            "eTag": "f7e4c7076761a42a871e978c8691c676",
        },
        "output_2": {
            "store": "0",  # <---Here is the legacy issue
            "path": "50339632-ee1d-11ec-a0c2-02420a0194e4/23b1522f-225f-5a4c-9158-c4c19a70d4a8/log.tgz",
            "eTag": "badfe49a41ef260bd5c148eb477aa1aa",
        },
    }

    for i in range(1, 3):
        port_meta = comp_tasks_schema["outputs"][f"output_{i}"]
        value = comp_tasks_outputs[f"output_{i}"]

        p = Port(key="port-name-goes-here", value=value, **port_meta)
