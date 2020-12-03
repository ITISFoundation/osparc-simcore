from typing import Dict
from uuid import uuid4

import pytest
from pydantic import ValidationError
from simcore_sdk.node_ports_v2.links import PortLink


@pytest.mark.parametrize(
    "port_link",
    [
        {"nodeUuid": f"{uuid4()}"},
        {"output": "some stuff"},
        {"nodeUuid": "some stuff", "output": "some stuff"},
    ],
)
def test_invalid_port_link(port_link: Dict[str, str]):
    with pytest.raises(ValidationError):
        PortLink(**port_link)
