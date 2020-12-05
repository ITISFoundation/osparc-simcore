from typing import Any, Dict, Type, Union

import pytest
from _pytest.mark import param
from simcore_sdk.node_ports_v2.ports_mapping import InputsList, OutputsList


@pytest.mark.parametrize("port_class", [InputsList, OutputsList])
def test_empty_ports_mapping_supports_dict_access(
    port_class: Type[Union[InputsList, OutputsList]]
):
    instance = port_class(**{"__root__": {}})
    assert not instance.items()
    assert not instance.values()
    assert len(instance) == 0
