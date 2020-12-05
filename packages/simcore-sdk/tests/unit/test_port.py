# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=no-member
# pylint:disable=protected-access
import re
import shutil
import tempfile
from asyncio import Future
from collections import namedtuple
from pathlib import Path
from random import randint
from typing import Any, Dict, Optional, Type, Union

import pytest
from aiohttp.client import ClientSession
from pydantic.error_wrappers import ValidationError
from simcore_sdk.node_ports import config
from simcore_sdk.node_ports.exceptions import InvalidItemTypeError
from simcore_sdk.node_ports_v2.links import DownloadLink, FileLink, PortLink
from simcore_sdk.node_ports_v2.port import Port
from yarl import URL


@pytest.fixture(scope="module")
def project_id() -> str:
    return "cd0d8dbb-3263-44dc-921c-49c075ac0dd9"


@pytest.fixture(scope="module")
def node_uuid() -> str:
    return "609b7af4-6861-4aa7-a16e-730ea8125190"


@pytest.fixture(scope="module")
def user_id() -> str:
    return str(randint(1, 666))


THIS_NODE_FILE_NAME: str = f"{tempfile.gettempdir()}/this_node_file.txt"
DOWNLOAD_FILE_DIR: Path = Path(tempfile.gettempdir(), "simcorefiles")
ANOTHER_NODE_FILE_NAME: Path = Path(tempfile.gettempdir(), "another_node_file.txt")


@pytest.fixture
def this_node_file() -> Path:
    file_path = Path(THIS_NODE_FILE_NAME)
    file_path.write_text("some dummy data")
    assert file_path.exists()
    yield file_path
    if file_path.exists():
        file_path.unlink()


@pytest.fixture
def another_node_file() -> Path:
    file_path = Path(tempfile.gettempdir(), "another_node_file.txt")
    file_path.write_text("some dummy data")
    assert file_path.exists()
    yield file_path
    if file_path.exists():
        file_path.unlink()


@pytest.fixture
def downloaded_file_folder() -> Path:
    destination_path = DOWNLOAD_FILE_DIR
    yield destination_path
    if destination_path.exists():
        shutil.rmtree(destination_path)


@pytest.fixture
async def mock_download_file(
    monkeypatch,
    this_node_file: Path,
    project_id: str,
    node_uuid: str,
    downloaded_file_folder: Path,
):
    async def mock_download_file_from_link(
        download_link: URL,
        local_folder: Path,
        session: Optional[ClientSession] = None,
        file_name: Optional[str] = None,
    ) -> Path:
        assert str(local_folder).startswith(str(DOWNLOAD_FILE_DIR))
        destination_path = local_folder / this_node_file.name
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(this_node_file, destination_path)
        return destination_path

    from simcore_sdk.node_ports import filemanager

    monkeypatch.setattr(
        filemanager, "download_file_from_link", mock_download_file_from_link
    )


@pytest.fixture
async def mock_upload_file(mocker):
    mock = mocker.patch(
        "simcore_sdk.node_ports.filemanager.upload_file",
        return_value=Future(),
    )
    mock.return_value.set_result("0")
    yield mock


@pytest.fixture(autouse=True)
def node_ports_config(
    loop,
    storage_v0_subsystem_mock,
    mock_download_file,
    mock_upload_file,
    project_id: str,
    user_id: str,
    node_uuid: str,
):
    config.USER_ID = user_id
    config.PROJECT_ID = project_id
    config.NODE_UUID = node_uuid
    config.STORAGE_ENDPOINT = "storage:8080"


def camel_to_snake(name):
    name = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", name).lower()


PortParams = namedtuple(
    "PortParams",
    "port_cfg, exp_value_type, exp_value_converter, exp_value, exp_get_value, new_value, exp_new_value, exp_new_get_value",
)


def create_valid_port_config(conf_type: str, **kwargs) -> Dict[str, Any]:
    valid_config = {
        "key": f"some_{conf_type}",
        "label": "some label",
        "description": "some description",
        "type": conf_type,
        "displayOrder": 2.3,
    }
    valid_config.update(kwargs)
    return valid_config


@pytest.mark.parametrize(
    "port_cfg, exp_value_type, exp_value_converter, exp_value, exp_get_value, new_value, exp_new_value, exp_new_get_value",
    [
        pytest.param(
            *PortParams(
                port_cfg=create_valid_port_config("integer", defaultValue=3),
                exp_value_type=(int),
                exp_value_converter=int,
                exp_value=3,
                exp_get_value=3,
                new_value=7,
                exp_new_value=7,
                exp_new_get_value=7,
            ),
            id="integer value with default",
        ),
        pytest.param(
            *PortParams(
                port_cfg=create_valid_port_config("number", defaultValue=-23.45),
                exp_value_type=(float),
                exp_value_converter=float,
                exp_value=-23.45,
                exp_get_value=-23.45,
                new_value=7,
                exp_new_value=7.0,
                exp_new_get_value=7.0,
            ),
            id="number value with default",
        ),
        pytest.param(
            *PortParams(
                port_cfg=create_valid_port_config("boolean", defaultValue=True),
                exp_value_type=(bool),
                exp_value_converter=bool,
                exp_value=True,
                exp_get_value=True,
                new_value=False,
                exp_new_value=False,
                exp_new_get_value=False,
            ),
            id="boolean value with default",
        ),
        pytest.param(
            *PortParams(
                port_cfg=create_valid_port_config(
                    "boolean", defaultValue=True, value=False
                ),
                exp_value_type=(bool),
                exp_value_converter=bool,
                exp_value=False,
                exp_get_value=False,
                new_value=True,
                exp_new_value=True,
                exp_new_get_value=True,
            ),
            id="boolean value with default and value",
        ),
        pytest.param(
            *PortParams(
                port_cfg=create_valid_port_config("data:*/*", key="no_file"),
                exp_value_type=(Path, str),
                exp_value_converter=Path,
                exp_value=None,
                exp_get_value=None,
                new_value=THIS_NODE_FILE_NAME,
                exp_new_value=FileLink(
                    store="0",
                    path=f"cd0d8dbb-3263-44dc-921c-49c075ac0dd9/609b7af4-6861-4aa7-a16e-730ea8125190/{Path(THIS_NODE_FILE_NAME).name}",
                ),
                exp_new_get_value=DOWNLOAD_FILE_DIR
                / "no_file"
                / Path(THIS_NODE_FILE_NAME).name,
            ),
            id="file type with no payload",
        ),
        pytest.param(
            *PortParams(
                port_cfg=create_valid_port_config(
                    "data:*/*",
                    key="no_file_with_default",
                    defaultValue=THIS_NODE_FILE_NAME,
                ),
                exp_value_type=(Path, str),
                exp_value_converter=Path,
                exp_value=None,
                exp_get_value=None,
                new_value=THIS_NODE_FILE_NAME,
                exp_new_value=FileLink(
                    store="0",
                    path=f"cd0d8dbb-3263-44dc-921c-49c075ac0dd9/609b7af4-6861-4aa7-a16e-730ea8125190/{Path(THIS_NODE_FILE_NAME).name}",
                ),
                exp_new_get_value=DOWNLOAD_FILE_DIR
                / "no_file_with_default"
                / Path(THIS_NODE_FILE_NAME).name,
            ),
            id="file link with no payload and default value",
        ),
        pytest.param(
            *PortParams(
                port_cfg=create_valid_port_config(
                    "data:*/*",
                    key="some_file",
                    value={"store": "0", "path": THIS_NODE_FILE_NAME},
                ),
                exp_value_type=(Path, str),
                exp_value_converter=Path,
                exp_value=FileLink(store="0", path=THIS_NODE_FILE_NAME),
                exp_get_value=DOWNLOAD_FILE_DIR
                / "some_file"
                / Path(THIS_NODE_FILE_NAME).name,
                new_value=None,
                exp_new_value=None,
                exp_new_get_value=None,
            ),
            id="file link with payload that get reset",
        ),
        pytest.param(
            *PortParams(
                port_cfg=create_valid_port_config(
                    "data:*/*",
                    key="some_file_on_datcore",
                    value={
                        "store": "1",
                        "path": THIS_NODE_FILE_NAME,
                        "dataset": "some blahblah",
                        "label": "some blahblah",
                    },
                ),
                exp_value_type=(Path, str),
                exp_value_converter=Path,
                exp_value=FileLink(
                    store="1",
                    path=THIS_NODE_FILE_NAME,
                    dataset="some blahblah",
                    label="some blahblah",
                ),
                exp_get_value=DOWNLOAD_FILE_DIR
                / "some_file_on_datcore"
                / Path(THIS_NODE_FILE_NAME).name,
                new_value=THIS_NODE_FILE_NAME,
                exp_new_value=FileLink(
                    store="0",
                    path=f"cd0d8dbb-3263-44dc-921c-49c075ac0dd9/609b7af4-6861-4aa7-a16e-730ea8125190/{Path(THIS_NODE_FILE_NAME).name}",
                ),
                exp_new_get_value=DOWNLOAD_FILE_DIR
                / "some_file_on_datcore"
                / Path(THIS_NODE_FILE_NAME).name,
            ),
            id="file link with payload on store 1",
        ),
        pytest.param(
            *PortParams(
                port_cfg=create_valid_port_config(
                    "data:*/*",
                    key="download_link",
                    value={
                        "downloadLink": "https://raw.githubusercontent.com/ITISFoundation/osparc-simcore/master/README.md"
                    },
                ),
                exp_value_type=(Path, str),
                exp_value_converter=Path,
                exp_value=DownloadLink(
                    downloadLink="https://raw.githubusercontent.com/ITISFoundation/osparc-simcore/master/README.md"
                ),
                exp_get_value=DOWNLOAD_FILE_DIR
                / "download_link"
                / Path(THIS_NODE_FILE_NAME).name,
                new_value=THIS_NODE_FILE_NAME,
                exp_new_value=FileLink(
                    store="0",
                    path=f"cd0d8dbb-3263-44dc-921c-49c075ac0dd9/609b7af4-6861-4aa7-a16e-730ea8125190/{Path(THIS_NODE_FILE_NAME).name}",
                ),
                exp_new_get_value=DOWNLOAD_FILE_DIR
                / "download_link"
                / Path(THIS_NODE_FILE_NAME).name,
            ),
            id="download link file type gets set back on store",
        ),
        pytest.param(
            *PortParams(
                port_cfg=create_valid_port_config(
                    "data:*/*",
                    key="file_port_link",
                    value={
                        "nodeUuid": "238e5b86-ed65-44b0-9aa4-f0e23ca8a083",
                        "output": "the_output_of_that_node",
                    },
                ),
                exp_value_type=(Path, str),
                exp_value_converter=Path,
                exp_value=PortLink(
                    nodeUuid="238e5b86-ed65-44b0-9aa4-f0e23ca8a083",
                    output="the_output_of_that_node",
                ),
                exp_get_value=DOWNLOAD_FILE_DIR
                / "file_port_link"
                / Path(ANOTHER_NODE_FILE_NAME).name,
                new_value=THIS_NODE_FILE_NAME,
                exp_new_value=FileLink(
                    store="0",
                    path=f"cd0d8dbb-3263-44dc-921c-49c075ac0dd9/609b7af4-6861-4aa7-a16e-730ea8125190/{Path(THIS_NODE_FILE_NAME).name}",
                ),
                exp_new_get_value=DOWNLOAD_FILE_DIR
                / "file_port_link"
                / Path(THIS_NODE_FILE_NAME).name,
            ),
            id="file node link type gets set back on store",
        ),
        pytest.param(
            *PortParams(
                port_cfg=create_valid_port_config(
                    "number",
                    key="number_port_link",
                    value={
                        "nodeUuid": "238e5b86-ed65-44b0-9aa4-f0e23ca8a083",
                        "output": "the_output_of_that_node",
                    },
                ),
                exp_value_type=(float),
                exp_value_converter=float,
                exp_value=PortLink(
                    nodeUuid="238e5b86-ed65-44b0-9aa4-f0e23ca8a083",
                    output="the_output_of_that_node",
                ),
                exp_get_value=562.45,
                new_value=None,
                exp_new_value=None,
                exp_new_get_value=None,
            ),
            id="number node link type gets reset",
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
    this_node_file: Path,
    another_node_file: Path,
):
    class FakeNodePorts:
        async def get(self, key):
            # this gets called when a node links to another node we return the get value but for files it needs to be a real one
            return (
                another_node_file
                if port_cfg["type"].startswith("data:")
                else exp_get_value
            )

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
    if exp_get_value is None:
        assert await port.get() == None
    else:
        assert await port.get() == exp_get_value

    # set a new value
    await port.set(new_value)
    assert port.value == exp_new_value
    if exp_new_get_value is None:
        assert await port.get() == None
    else:
        assert await port.get() == exp_new_get_value


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


@pytest.mark.parametrize(
    "port_cfg", [(create_valid_port_config("data:*/*", key="set_some_inexisting_file"))]
)
async def test_invalid_file_type_setter(port_cfg: Dict[str, Any]):
    port = Port(**port_cfg)
    # set a file that does not exist
    with pytest.raises(InvalidItemTypeError):
        await port.set("some/dummy/file/name")

    # set a folder fails too
    with pytest.raises(InvalidItemTypeError):
        await port.set(Path(__file__).parent)
