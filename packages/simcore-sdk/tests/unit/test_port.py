# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=no-member
# pylint:disable=protected-access
import re
from pathlib import Path
from typing import Any, Dict, Type, Union

import pytest
from pydantic.error_wrappers import ValidationError
from simcore_sdk.node_ports_v2.port import Port


def camel_to_snake(name):
    name = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", name).lower()


@pytest.mark.parametrize(
    "port_cfg, exp_value_type, exp_value_converter, exp_value",
    [
        (
            {
                "key": "some_integer",
                "label": "some label",
                "description": "some description",
                "type": "integer",
                "displayOrder": 2.3,
                "defaultValue": 3,
            },
            (int),
            int,
            3,
        ),
        (
            {
                "key": "some_number",
                "label": "",
                "description": "",
                "type": "number",
                "displayOrder": 2.3,
                "defaultValue": -23.45,
            },
            (float),
            float,
            -23.46,
        ),
        (
            {
                "key": "some_boolean",
                "label": "",
                "description": "",
                "type": "boolean",
                "displayOrder": 2.3,
                "defaultValue": True,
            },
            (bool),
            bool,
            True,
        ),
        (
            {
                "key": "some_boolean",
                "label": "",
                "description": "",
                "type": "boolean",
                "displayOrder": 2.3,
                "defaultValue": True,
                "value": False,
            },
            (bool),
            bool,
            False,
        ),
        (
            {
                "key": "some_file",
                "label": "",
                "description": "",
                "type": "data:*/*",
                "displayOrder": 2.3,
            },
            (Path, str),
            Path,
            None,
        ),
        (
            {
                "key": "some_file_with_file_in_defaulvalue",
                "label": "",
                "description": "",
                "type": "data:*/*",
                "displayOrder": 2.3,
                "defaultValue": __file__,
            },
            (Path, str),
            Path,
            None,
        ),
    ],
)
async def test_valid_port(
    port_cfg: Dict[str, Any],
    exp_value_type: Type[Union[int, float, bool, str, Path]],
    exp_value_converter: Type[Union[int, float, bool, str, Path]],
    exp_value: Union[int, float, bool, str, Path],
):
    port = Port(**port_cfg)

    for k, v in port_cfg.items():
        camel_key = camel_to_snake(k)
        if k == "type":
            camel_key = "property_type"
        assert v == getattr(port, camel_key)

    assert port._py_value_type == exp_value_type
    assert port._py_value_converter == exp_value_converter

    assert port.value == exp_value
    if exp_value:
        assert await port.get() == exp_value_converter(exp_value)


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
        {
            "key": "some_file_with_file_in_value",
            "label": "",
            "description": "",
            "type": "data:*/*",
            "displayOrder": 2.3,
            "value": __file__,
        },
    ],
)
def test_invalid_port(port_cfg: Dict[str, Any]):
    with pytest.raises(ValidationError):
        Port(**port_cfg)
