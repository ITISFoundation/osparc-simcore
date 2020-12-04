# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=no-member
# pylint:disable=protected-access
import re
from asyncio import Future
from collections import namedtuple
from pathlib import Path
from typing import Any, Dict, Type, Union

import pytest
from pydantic.error_wrappers import ValidationError
from simcore_sdk.node_ports import config
from simcore_sdk.node_ports_v2.links import DownloadLink, FileLink, PortLink
from simcore_sdk.node_ports_v2.port import Port


@pytest.fixture
async def mock_download_file(mocker):
    mock = mocker.patch(
        "simcore_sdk.node_ports.filemanager.download_file_from_link",
        return_value=Future(),
    )
    mock.return_value.set_result(__file__)
    yield mock


@pytest.fixture(autouse=True)
def node_ports_config(loop, storage_v0_subsystem_mock, mock_download_file):
    config.USER_ID = "666"
    config.STORAGE_ENDPOINT = "storage:8080"


def camel_to_snake(name):
    name = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", name).lower()


PortParams = namedtuple(
    "PortParams",
    "port_cfg, exp_value_type, exp_value_converter, exp_value, exp_get_value, new_value, exp_new_value, exp_new_get_value",
)


@pytest.mark.parametrize(
    "port_cfg, exp_value_type, exp_value_converter, exp_value, exp_get_value, new_value, exp_new_value, exp_new_get_value",
    [
        PortParams(
            port_cfg={
                "key": "some_integer",
                "label": "some label",
                "description": "some description",
                "type": "integer",
                "displayOrder": 2.3,
                "defaultValue": 3,
            },
            exp_value_type=(int),
            exp_value_converter=int,
            exp_value=3,
            exp_get_value=3,
            new_value=7,
            exp_new_value=7,
            exp_new_get_value=7,
        ),
        PortParams(
            port_cfg={
                "key": "some_number",
                "label": "",
                "description": "",
                "type": "number",
                "displayOrder": 2.3,
                "defaultValue": -23.45,
            },
            exp_value_type=(float),
            exp_value_converter=float,
            exp_value=-23.45,
            exp_get_value=-23.45,
            new_value=7,
            exp_new_value=7.0,
            exp_new_get_value=7.0,
        ),
        PortParams(
            port_cfg={
                "key": "some_boolean",
                "label": "",
                "description": "",
                "type": "boolean",
                "displayOrder": 2.3,
                "defaultValue": True,
            },
            exp_value_type=(bool),
            exp_value_converter=bool,
            exp_value=True,
            exp_get_value=True,
            new_value=False,
            exp_new_value=False,
            exp_new_get_value=False,
        ),
        PortParams(
            port_cfg={
                "key": "some_boolean",
                "label": "",
                "description": "",
                "type": "boolean",
                "displayOrder": 2.3,
                "defaultValue": True,
                "value": False,
            },
            exp_value_type=(bool),
            exp_value_converter=bool,
            exp_value=False,
            exp_get_value=False,
            new_value=True,
            exp_new_value=True,
            exp_new_get_value=True,
        ),
        PortParams(
            port_cfg={
                "key": "some_file",
                "label": "",
                "description": "",
                "type": "data:*/*",
                "displayOrder": 2.3,
            },
            exp_value_type=(Path, str),
            exp_value_converter=Path,
            exp_value=None,
            exp_get_value=None,
            new_value=__file__,
            exp_new_value=FileLink(store="0", path=__file__),
            exp_new_get_value=__file__,
        ),
        PortParams(
            port_cfg={
                "key": "some_file_with_file_in_defaulvalue",
                "label": "",
                "description": "",
                "type": "data:*/*",
                "displayOrder": 2.3,
                "defaultValue": __file__,
            },
            exp_value_type=(Path, str),
            exp_value_converter=Path,
            exp_value=None,
            exp_get_value=None,
            new_value=__file__,
            exp_new_value=FileLink(store="0", path=__file__),
            exp_new_get_value=__file__,
        ),
        PortParams(
            port_cfg={
                "key": "some_file_with_file_in_storage",
                "label": "",
                "description": "",
                "type": "data:*/*",
                "displayOrder": 2.3,
                "value": {"store": "0", "path": __file__},
            },
            exp_value_type=(Path, str),
            exp_value_converter=Path,
            exp_value=FileLink(store="0", path=__file__),
            exp_get_value=__file__,
            new_value=None,
            exp_new_value=None,
            exp_new_get_value=None,
        ),
        PortParams(
            port_cfg={
                "key": "some_file_with_file_in_storage",
                "label": "",
                "description": "",
                "type": "data:*/*",
                "displayOrder": 2.3,
                "value": {
                    "store": "1",
                    "path": __file__,
                    "dataset": "some blahblah",
                    "label": "some blahblah",
                },
            },
            exp_value_type=(Path, str),
            exp_value_converter=Path,
            exp_value=FileLink(
                store="1", path=__file__, dataset="some blahblah", label="some blahblah"
            ),
            exp_get_value=__file__,
            new_value=__file__,
            exp_new_value=FileLink(store="0", path=__file__),
            exp_new_get_value=__file__,
        ),
        PortParams(
            port_cfg={
                "key": "some_file_with_file_as_download_link",
                "label": "",
                "description": "",
                "type": "data:*/*",
                "displayOrder": 2.3,
                "value": {
                    "downloadLink": "https://raw.githubusercontent.com/ITISFoundation/osparc-simcore/master/README.md",
                },
            },
            exp_value_type=(Path, str),
            exp_value_converter=Path,
            exp_value=DownloadLink(
                downloadLink="https://raw.githubusercontent.com/ITISFoundation/osparc-simcore/master/README.md"
            ),
            exp_get_value=__file__,
            new_value=__file__,
            exp_new_value=FileLink(store="0", path=__file__),
            exp_new_get_value=__file__,
        ),
        PortParams(
            port_cfg={
                "key": "some_file_with_file_as_port_link",
                "label": "",
                "description": "",
                "type": "data:*/*",
                "displayOrder": 2.3,
                "value": {
                    "nodeUuid": "238e5b86-ed65-44b0-9aa4-f0e23ca8a083",
                    "output": "the_output_of_that_node",
                },
            },
            exp_value_type=(Path, str),
            exp_value_converter=Path,
            exp_value=PortLink(
                nodeUuid="238e5b86-ed65-44b0-9aa4-f0e23ca8a083",
                output="the_output_of_that_node",
            ),
            exp_get_value=__file__,
            new_value=__file__,
            exp_new_value=FileLink(store="0", path=__file__),
            exp_new_get_value=__file__,
        ),
    ],
)
async def test_valid_port(
    port_cfg: Dict[str, Any],
    exp_value_type: Type[Union[int, float, bool, str, Path]],
    exp_value_converter: Type[Union[int, float, bool, str, Path]],
    exp_value: Union[int, float, bool, str, Path, FileLink, DownloadLink, PortLink],
    exp_get_value: Union[int, float, bool, str, Path],
    new_value: Union[int, float, bool, str, Path],
    exp_new_value: Union[int, float, bool, str, Path, FileLink],
    exp_new_get_value: Union[int, float, bool, str, Path],
):
    class FakeNodePorts:
        async def get(self, key):
            return exp_get_value

        async def _node_ports_creator_cb(self, node_uuid: str):
            return FakeNodePorts()

        async def save_to_db_cb(self, node_ports):
            return

    fake_node_ports = FakeNodePorts()
    port = Port(**port_cfg)
    port._node_ports = fake_node_ports

    # check schema
    for k, v in port_cfg.items():
        camel_key = camel_to_snake(k)
        if k == "type":
            camel_key = "property_type"
        if k != "value":
            assert v == getattr(port, camel_key)

    # check payload
    assert port._py_value_type == exp_value_type
    assert port._py_value_converter == exp_value_converter

    assert port.value == exp_value
    if exp_value:
        assert await port.get() == exp_value_converter(exp_get_value)

    # set a new value
    await port.set(new_value)


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
