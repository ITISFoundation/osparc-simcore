from uuid import uuid4

import pytest
from pydantic import ValidationError
from simcore_sdk.node_ports_v2.links import DownloadLink, FileLink, PortLink


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
def test_invalid_port_link(port_link: dict[str, str]):
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
def test_invalid_download_link(download_link: dict[str, str]):
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
def test_invalid_file_link(file_link: dict[str, str]):
    with pytest.raises(ValidationError):
        FileLink(**file_link)
