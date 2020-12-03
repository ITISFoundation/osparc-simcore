from typing import Any, Dict

import pytest
from pydantic.error_wrappers import ValidationError
from simcore_sdk.node_ports_v2.port import Port


@pytest.mark.parametrize(
    "port_cfg",
    [
        {
            "key": "some_key",
            "label": "some label",
            "description": "some description",
            "type": "integer",
            "displayOrder": 2.3,
        },
        {
            "key": "some_key",
            "label": "",
            "description": "",
            "type": "integer",
            "displayOrder": 2.3,
        },
    ],
)
def test_valid_port(port_cfg: Dict[str, Any]):
    Port(**port_cfg)


@pytest.mark.parametrize(
    "port_cfg",
    [
        {
            "key": "some.key",
            "label": "some label",
            "description": "some description",
            "type": "integer",
            "displayOrder": 2.3,
        },
        {
            "key": "some:key",
            "label": "",
            "description": "",
            "type": "integer",
            "displayOrder": 2.3,
        },
        {
            "key": "some_key",
            "label": "",
            "description": "",
            "type": "blahblah",
            "displayOrder": 2.3,
        },
    ],
)
def test_invalid_port(port_cfg: Dict[str, Any]):
    with pytest.raises(ValidationError):
        Port(**port_cfg)
