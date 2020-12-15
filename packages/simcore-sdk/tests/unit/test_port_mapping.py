from typing import Any, Dict, Type, Union

import pytest
from simcore_sdk.node_ports_v2 import exceptions
from simcore_sdk.node_ports_v2.ports_mapping import InputsList, OutputsList
from utils_port_v2 import create_valid_port_config


##################### TESTS
@pytest.mark.parametrize("port_class", [InputsList, OutputsList])
def test_empty_ports_mapping(port_class: Type[Union[InputsList, OutputsList]]):
    port_mapping = port_class(**{"__root__": {}})
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
    port_mapping = port_class(**{"__root__": port_cfgs})

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
