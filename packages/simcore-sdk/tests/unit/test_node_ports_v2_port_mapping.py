# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from collections import deque
from pprint import pprint
from typing import Any

import pytest
from models_library.services import ServiceInput
from pydantic import Field, TypeAdapter, ValidationError
from simcore_sdk.node_ports_v2 import exceptions
from simcore_sdk.node_ports_v2.port import Port
from simcore_sdk.node_ports_v2.ports_mapping import InputsList, OutputsList
from typing_extensions import Annotated
from utils_port_v2 import create_valid_port_config


@pytest.mark.parametrize("port_class", [InputsList, OutputsList])
def test_empty_ports_mapping(port_class: type[InputsList | OutputsList]):
    port_mapping = port_class(root={})
    assert not port_mapping.items()
    assert not port_mapping.values()
    assert not port_mapping.keys()
    assert len(port_mapping) == 0
    for port_key in port_mapping:
        # it should be empty
        assert True, f"should be empty, got {port_key}"


@pytest.mark.parametrize("port_class", [InputsList, OutputsList])
def test_filled_ports_mapping(port_class: type[InputsList | OutputsList]):
    port_cfgs: dict[str, Any] = {}
    for t in ["integer", "number", "boolean", "string"]:
        port = create_valid_port_config(t)
        port_cfgs[port["key"]] = port
    port_cfgs["some_file"] = create_valid_port_config("data:*/*", key="some_file")

    port_mapping = port_class(root=port_cfgs)

    # two ways to construct instances of __root__
    assert port_class.model_validate(port_cfgs) == port_mapping

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

    inputs = InputsList(root={})
    outputs = OutputsList(root={})

    assert isinstance(inputs, InputsList)
    assert not isinstance(inputs, OutputsList)

    assert isinstance(outputs, OutputsList)
    assert not isinstance(outputs, InputsList)


@pytest.fixture
def fake_port_meta() -> dict[str, Any]:
    """Service port metadata: defines a list of non-negative numbers"""
    schema = {
        **TypeAdapter(list[Annotated[float, Field(ge=0)]]).json_schema(),
        "title": "list[non-negative number]",
    }

    schema.update(
        description="Port with an array of numbers",
        x_unit="millimeter",
    )

    port_model = ServiceInput.from_json_schema(port_schema=schema)
    return port_model.model_dump(exclude_unset=True, by_alias=True)


def test_validate_port_value_against_schema(fake_port_meta: dict[str, Any]):
    # A simcore-sdk Port instance is a combination of both
    #  - the port's metadata
    #  - the port's value
    port_meta = fake_port_meta
    port_value = {"key": "port_1", "value": [1, -2, 3, -4.0]}

    with pytest.raises(ValidationError) as err_info:
        Port(**port_meta, **port_value)

    assert isinstance(err_info.value, ValidationError)
    assert len(err_info.value.errors()) == 1

    error = err_info.value.errors()[0]
    # {
    #   'loc': ('value'),
    #   'msg': 'port_1 value does not fulfill content schema: ',
    #   'type': 'value_error.port_validation.schema_error',
    #   'ctx': {'port_key': 'port_1', 'schema_error': <ValidationError: '-2 is less than the minimum of 0'>}
    # }

    assert error["loc"] == ("value",)
    assert "-2 is less than the minimum of 0" in error["msg"]
    assert error["type"] == "value_error"

    assert "ctx" in error
    assert error["ctx"]["error"].port_key == "port_1"

    schema_error_message = error["ctx"]["error"].schema_error_message
    schema_error_path = error["ctx"]["error"].schema_error_path

    assert schema_error_message in error["msg"]
    assert schema_error_path == deque([1])


def test_validate_iolist_against_schema(fake_port_meta: dict[str, Any]):
    # Check how errors propagate from a single Port to InputsList

    # reference port
    port_meta = fake_port_meta
    port_value = {"key": "port_1", "value": [1, -2, 3, -4.0]}
    ports = [
        {**port_meta, **port_value},
    ]
    expected_port_with_errors = [
        port_value["key"],
    ]

    # same value, different key
    port_value["key"] = "port_2"
    ports.append({**port_meta, **port_value})
    expected_port_with_errors.append(port_value["key"])

    # all valid values
    port_value = {"key": "port_3", "value": [1, 2, 3, 4.3]}
    ports.append({**port_meta, **port_value})

    # invalid values
    port_value = {"key": "port_4", "value": ["wrong", 2, 3, 4.3]}
    ports.append({**port_meta, **port_value})
    expected_port_with_errors.append(port_value["key"])

    # ----

    with pytest.raises(ValidationError) as err_info:
        InputsList.model_validate({p["key"]: p for p in ports})

    # ---
    assert isinstance(err_info.value, ValidationError)
    assert len(err_info.value.errors()) == len(expected_port_with_errors)

    port_with_errors = []
    for error in err_info.value.errors():
        error_loc = error["loc"]
        assert "ctx" in error
        port_key = error["ctx"]["error"].port_key

        # path hierachy
        assert error_loc[0] == port_key, f"{error_loc=}"
        assert error_loc[1] == "value", f"{error_loc=}"

        assert error["type"] == "value_error"
        port_with_errors.append(port_key)
        pprint(error)

    assert port_with_errors == expected_port_with_errors
