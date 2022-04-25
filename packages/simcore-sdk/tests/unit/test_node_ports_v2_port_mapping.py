import json
from collections import deque
from typing import Any, Dict, List, Type, Union

import jsonschema
import pytest
from models_library.services import ServiceInput
from pydantic import ValidationError, confloat, schema_of
from simcore_sdk.node_ports_v2 import exceptions
from simcore_sdk.node_ports_v2.port import Port
from simcore_sdk.node_ports_v2.ports_mapping import InputsList, OutputsList
from utils_port_v2 import create_valid_port_config


@pytest.mark.parametrize("port_class", [InputsList, OutputsList])
def test_empty_ports_mapping(port_class: Type[Union[InputsList, OutputsList]]):
    port_mapping = port_class(__root__={})
    assert not port_mapping.items()
    assert not port_mapping.values()
    assert not port_mapping.keys()
    assert len(port_mapping) == 0
    for port_key in port_mapping:
        # it should be empty
        assert True, f"should be empty, got {port_key}"


@pytest.mark.parametrize("port_class", [InputsList, OutputsList])
def test_filled_ports_mapping(port_class: Type[Union[InputsList, OutputsList]]):
    port_cfgs: Dict[str, Any] = {}
    for t in ["integer", "number", "boolean", "string"]:
        port = create_valid_port_config(t)
        port_cfgs[port["key"]] = port
    port_cfgs["some_file"] = create_valid_port_config("data:*/*", key="some_file")

    port_mapping = port_class(__root__=port_cfgs)

    # two ways to construct instances of __root__
    assert port_class.parse_obj(port_cfgs) == port_mapping

    assert len(port_mapping) == len(port_cfgs)
    for port_key, port_value in port_mapping.items():
        assert port_key in port_mapping
        assert port_key in port_cfgs

        # just to make use of the variable and check the pydantic overloads are working correctly
        assert port_mapping[port_key] == port_value

    for index, port_key in enumerate(port_cfgs):
        assert port_mapping[index] == port_mapping[port_key]

    with pytest.raises(exceptions.UnboundPortError):
        _ = port_mapping[len(port_cfgs)]
    with pytest.raises(exceptions.UnboundPortError):
        _ = port_mapping["whatever"]


def test_io_ports_are_not_aliases():
    # prevents creating alises as InputsList = PortsMappings

    inputs = InputsList(__root__={})
    outputs = OutputsList(__root__={})

    assert isinstance(inputs, InputsList)
    assert not isinstance(inputs, OutputsList)

    assert isinstance(outputs, OutputsList)
    assert not isinstance(outputs, InputsList)


def test_input_lists_with_port_schema_validation_errors():
    expected_port_with_errors = []

    # A simcore-sdk Port instance is a combination of both
    #  - the port's metadata
    #  - the port's value
    #

    schema = schema_of(
        List[confloat(ge=0)],
        title="list[non-negative number]",
    )
    schema.update(
        description="Port with an array of numbers",
        x_unit="millimeter",
    )

    port_meta = ServiceInput.from_json_schema(port_schema=schema).dict(
        exclude_unset=True, by_alias=True
    )

    port_value = {"key": "port_1", "value": [1, -2, 3, -4.0]}
    expected_port_with_errors.append(port_value["key"])

    with pytest.raises(ValidationError) as err_info:
        Port(**port_meta, **port_value)

    assert isinstance(err_info.value, ValidationError)
    assert len(err_info.value.errors()) == 1
    error = err_info.value.errors()[0]
    # this is how the error entry looks like
    # {
    #   'loc': ('value'),
    #   'msg': 'port_1 value does not fulfill content schema: -2 is less than the minimum of 0',
    #   'type': 'value_error.port_schema_validation_error',
    #   'ctx': {'port_key': 'port_1', 'schema_error': <ValidationError: '-2 is less than the minimum of 0'>}
    # }
    assert error["loc"] == ("value",)
    assert error["ctx"]["port_key"] == "port_1"

    assert isinstance(error["ctx"]["schema_error"], jsonschema.ValidationError)
    schema_error = error["ctx"]["schema_error"]
    # schema_error.message: str
    assert schema_error.path == deque([1])
    assert schema_error.schema_path == deque(["items", "minimum"])
    assert schema_error.schema == {"type": "number", "minimum": 0}
    assert schema_error.context == []
    # schema_error.cause = self.__cause__ = cause
    assert schema_error.validator == "minimum"
    assert schema_error.validator_value == 0
    # schema_error.instance = instance
    assert schema_error.parent is None

    # An InputsList is a Dict[PortKey, Port]
    #   Creates an inputlist with several invalid ports
    #
    expected_port_with_errors = [
        port_value["key"],
    ]
    ports = []

    ports.append({**port_meta, **port_value})

    port_value["key"] = "port_2"
    expected_port_with_errors.append(port_value["key"])
    ports.append({**port_meta, **port_value})

    port_value = {"key": "port_3", "value": [1, 2, 3, 4.3]}
    ports.append({**port_meta, **port_value})

    port_value = {"key": "port_4", "value": ["wrong", 2, 3, 4.3]}
    expected_port_with_errors.append(port_value["key"])
    ports.append({**port_meta, **port_value})

    with pytest.raises(ValidationError) as err_info:
        InputsList.parse_obj({p["key"]: p for p in ports})

    # Collect only port errors
    assert isinstance(err_info.value, ValidationError)
    assert len(err_info.value.errors()) == len(expected_port_with_errors)

    port_with_errors = []
    for error in err_info.value.errors():
        loc = error["loc"]
        if len(loc) == 3 and (loc[0], loc[2]) == ("__root__", "value"):
            port_name = loc[1]
            port_with_errors.append(port_name)

        assert error["loc"] == ("__root__", port_name, "value")
        assert error["type"] == "value_error.port_schema_validation_error"
        print(json.dumps(error))

    assert port_with_errors == expected_port_with_errors
