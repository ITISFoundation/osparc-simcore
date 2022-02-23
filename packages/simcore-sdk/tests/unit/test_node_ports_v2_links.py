from typing import Dict, get_args
from uuid import uuid4

import pytest
from models_library.projects_nodes import InputTypes, OutputTypes
from models_library.projects_nodes_io import BaseFileLink
from pydantic import ValidationError
from simcore_sdk.node_ports_v2.links import (
    DataItemValue,
    DownloadLink,
    FileLink,
    PortLink,
)


def test_valid_port_link():
    port_link = {"nodeUuid": f"{uuid4()}", "output": "some_key"}
    PortLink(**port_link)


@pytest.mark.parametrize(
    "port_link",
    [
        {"nodeUuid": f"{uuid4()}"},
        {"output": "some_stuff"},
        {"nodeUuid": "some stuff", "output": "some_stuff"},
        {"nodeUuid": "", "output": "some stuff"},
        {"nodeUuid": f"{uuid4()}", "output": ""},
        {"nodeUuid": f"{uuid4()}", "output": "some.key"},
        {"nodeUuid": f"{uuid4()}", "output": "some:key"},
    ],
)
def test_invalid_port_link(port_link: Dict[str, str]):
    with pytest.raises(ValidationError):
        PortLink(**port_link)


@pytest.mark.parametrize(
    "download_link",
    [
        {"downloadLink": ""},
        {"downloadLink": "some stuff"},
        {"label": "some stuff"},
    ],
)
def test_invalid_download_link(download_link: Dict[str, str]):
    with pytest.raises(ValidationError):
        DownloadLink(**download_link)


@pytest.mark.parametrize(
    "file_link",
    [
        {"store": ""},
        {"store": "0", "path": ""},
        {"path": "/somefile/blahblah:"},
    ],
)
def test_invalid_file_link(file_link: Dict[str, str]):
    with pytest.raises(ValidationError):
        FileLink(**file_link)


def test_data_item_synced_with_project_nodes_io_types():
    # TODO: make sure things are in

    input_types = list(get_args(InputTypes))
    output_types = list(get_args(OutputTypes))

    assert FileLink in get_args(DataItemValue)
    # covers all BaseFileLink classes
    found = {arg for arg in input_types if issubclass(arg, BaseFileLink)}
    assert found
    for f in found:
        input_types.remove(f)

    found = {arg for arg in output_types if issubclass(arg, BaseFileLink)}
    assert found
    for f in found:
        output_types.remove(f)
