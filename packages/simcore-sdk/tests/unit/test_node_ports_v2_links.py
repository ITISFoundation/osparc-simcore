from typing import Any
from uuid import uuid4

import pytest
from pydantic import (
    AnyUrl,
    StrictBool,
    StrictFloat,
    StrictInt,
    StrictStr,
    ValidationError,
)
from simcore_sdk.node_ports_v2.links import (
    DataItemValue,
    DownloadLink,
    FileLink,
    PortLink,
)


def test_data_item_value_members_are_pinned():
    # Early warning if `DataItemValue` (links.py) changes: it used to be
    # documented as needing to stay "in sync" with
    # models_library.projects_nodes.InputTypes/OutputTypes, but it deliberately
    # deviates (StrictStr instead of str/Json, sdk-local PortLink/FileLink).
    # If this test fails, update it *and* the NOTE in links.py.
    assert DataItemValue.__args__ == (
        StrictBool,
        StrictInt,
        StrictFloat,
        StrictStr,
        DownloadLink,
        PortLink,
        FileLink,
        list[Any],  # arrays
        dict[str, Any],  # object
    )
    # sanity: AnyUrl is NOT part of DataItemValue (it appears in ItemValue)
    assert AnyUrl not in DataItemValue.__args__


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
