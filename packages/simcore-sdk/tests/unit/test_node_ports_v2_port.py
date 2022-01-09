# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=no-member
# pylint:disable=protected-access
# pylint:disable=too-many-arguments


import os
import re
import shutil
import tempfile
import threading
from collections import namedtuple
from pathlib import Path
from typing import Any, Dict, Iterator, Optional, Type, Union


import pytest
from aiohttp.client import ClientSession
from attr import dataclass
from pydantic.error_wrappers import ValidationError
from pytest_mock.plugin import MockerFixture
from simcore_sdk.node_ports_v2 import exceptions, node_config
from simcore_sdk.node_ports_v2.links import DownloadLink, FileLink, PortLink
from simcore_sdk.node_ports_v2.port import Port
from utils_port_v2 import create_valid_port_config
from yarl import URL


##################### HELPERS
def camel_to_snake(name):
    name = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", name).lower()


PortParams = namedtuple(
    "PortParams",
    "port_cfg, exp_value_type, exp_value_converter, exp_value, exp_get_value, new_value, exp_new_value, exp_new_get_value",
)


def this_node_file_name() -> Path:
    return Path(tempfile.gettempdir(), "this_node_file.txt")


def another_node_file_name() -> Path:
    return Path(tempfile.gettempdir(), "another_node_file.txt")


def download_file_folder_name() -> Path:
    return Path(tempfile.gettempdir(), "simcorefiles", f"{threading.get_ident()}")


def project_id() -> str:
    return "cd0d8dbb-3263-44dc-921c-49c075ac0dd9"


def node_uuid() -> str:
    return "609b7af4-6861-4aa7-a16e-730ea8125190"


def user_id() -> int:
    return 666


def simcore_store_id() -> str:
    return "0"


def datcore_store_id() -> str:
    return "1"


def e_tag() -> str:
    return "1212132546546321-1"


##################### FIXTURES


@pytest.fixture
def symlink_to_file_with_data() -> Iterator[Path]:
    file_name: Path = this_node_file_name()
    symlink_path = file_name
    assert not symlink_path.exists()
    file_path = file_name.parent / f"source_{file_name.name}"
    assert not file_path.exists()

    file_path.write_text("some dummy data")
    assert file_path.exists()
    os.symlink(file_path, symlink_path)
    assert symlink_path.exists()

    yield symlink_path

    symlink_path.unlink()
    assert not symlink_path.exists()
    file_path.unlink()
    assert not file_path.exists()


@pytest.fixture
def file_with_data() -> Iterator[Path]:
    file_name: Path = this_node_file_name()
    file_path = file_name
    assert not file_path.exists()
    file_path.write_text("some dummy data")
    assert file_path.exists()

    yield file_path

    file_path.unlink()
    assert not file_path.exists()


@pytest.fixture(
    params=[
        pytest.lazy_fixture("symlink_to_file_with_data"),
        pytest.lazy_fixture("file_with_data"),
    ]
)
def this_node_file(request) -> Iterator[Path]:
    yield request.param


@pytest.fixture
def another_node_file() -> Iterator[Path]:
    file_path = another_node_file_name()
    file_path.write_text("some dummy data")
    assert file_path.exists()
    yield file_path
    if file_path.exists():
        file_path.unlink()


@pytest.fixture
def download_file_folder() -> Iterator[Path]:
    destination_path = download_file_folder_name()
    destination_path.mkdir(parents=True, exist_ok=True)
    yield destination_path
    if destination_path.exists():
        shutil.rmtree(destination_path)


@pytest.fixture(scope="module", name="project_id")
def project_id_fixture() -> str:
    """NOTE: since pytest does not allow to use fixtures inside parametrizations,
    this trick allows to re-use the same function in a fixture with a same "fixture" name"""
    return project_id()


@pytest.fixture(scope="module", name="node_uuid")
def node_uuid_fixture() -> str:
    """NOTE: since pytest does not allow to use fixtures inside parametrizations,
    this trick allows to re-use the same function in a fixture with a same "fixture" name"""
    return node_uuid()


@pytest.fixture(scope="module", name="user_id")
def user_id_fixture() -> int:
    """NOTE: since pytest does not allow to use fixtures inside parametrizations,
    this trick allows to re-use the same function in a fixture with a same "fixture" name"""
    return user_id()


@pytest.fixture
async def mock_download_file(
    mocker: MockerFixture,
    this_node_file: Path,
    project_id: str,
    node_uuid: str,
    download_file_folder: Path,
):
    async def mock_download_file_from_link(
        download_link: URL,
        local_folder: Path,
        file_name: Optional[str] = None,
        client_session: Optional[ClientSession] = None,
    ) -> Path:
        assert str(local_folder).startswith(str(download_file_folder))
        destination_path = local_folder / this_node_file.name
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(this_node_file, destination_path)
        return destination_path

    mocker.patch(
        "simcore_sdk.node_ports_common.filemanager.get_download_link_from_s3",
        return_value="a fake link",
    )

    mocker.patch(
        "simcore_sdk.node_ports_common.filemanager.download_file_from_link",
        side_effect=mock_download_file_from_link,
    )


@pytest.fixture(scope="session", name="e_tag")
def e_tag_fixture() -> str:
    return "1212132546546321-1"


@pytest.fixture
async def mock_upload_file(mocker, e_tag):
    mock = mocker.patch(
        "simcore_sdk.node_ports_common.filemanager.upload_file",
        return_value=(simcore_store_id(), e_tag),
    )
    yield mock


@pytest.fixture
def common_fixtures(
    loop,
    storage_v0_service_mock,
    mock_download_file,
    mock_upload_file,
    this_node_file: Path,
    another_node_file: Path,
    download_file_folder: Path,
):
    """this module main fixture"""

    node_config.STORAGE_ENDPOINT = "storage:8080"


##################### TESTS
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
                new_value=str(this_node_file_name()),
                exp_new_value=FileLink(
                    store=simcore_store_id(),
                    path=f"{project_id()}/{node_uuid()}/{this_node_file_name().name}",
                    e_tag=e_tag(),
                ),
                exp_new_get_value=download_file_folder_name()
                / "no_file"
                / this_node_file_name().name,
            ),
            id="file type with no payload",
        ),
        pytest.param(
            *PortParams(
                port_cfg=create_valid_port_config(
                    "data:*/*",
                    key="no_file_with_default",
                    defaultValue=str(this_node_file_name()),
                ),
                exp_value_type=(Path, str),
                exp_value_converter=Path,
                exp_value=None,
                exp_get_value=None,
                new_value=this_node_file_name(),
                exp_new_value=FileLink(
                    store=simcore_store_id(),
                    path=f"{project_id()}/{node_uuid()}/{this_node_file_name().name}",
                    e_tag=e_tag(),
                ),
                exp_new_get_value=download_file_folder_name()
                / "no_file_with_default"
                / this_node_file_name().name,
            ),
            id="file link with no payload and default value",
        ),
        pytest.param(
            *PortParams(
                port_cfg=create_valid_port_config(
                    "data:*/*",
                    key="some_file",
                    value={
                        "store": simcore_store_id(),
                        "path": f"{project_id()}/{node_uuid()}/{this_node_file_name().name}",
                    },
                ),
                exp_value_type=(Path, str),
                exp_value_converter=Path,
                exp_value=FileLink(
                    store=simcore_store_id(),
                    path=f"{project_id()}/{node_uuid()}/{this_node_file_name().name}",
                ),
                exp_get_value=download_file_folder_name()
                / "some_file"
                / this_node_file_name().name,
                new_value=None,
                exp_new_value=None,
                exp_new_get_value=None,
            ),
            id="file link with payload that gets reset",
        ),
        pytest.param(
            *PortParams(
                port_cfg=create_valid_port_config(
                    "data:*/*",
                    key="some_file_with_file_to_key_map",
                    fileToKeyMap={
                        "a_new_fancy_name.csv": "some_file_with_file_to_key_map"
                    },
                    value={
                        "store": simcore_store_id(),
                        "path": f"{project_id()}/{node_uuid()}/{this_node_file_name().name}",
                    },
                ),
                exp_value_type=(Path, str),
                exp_value_converter=Path,
                exp_value=FileLink(
                    store=simcore_store_id(),
                    path=f"{project_id()}/{node_uuid()}/{this_node_file_name().name}",
                ),
                exp_get_value=download_file_folder_name()
                / "some_file_with_file_to_key_map"
                / "a_new_fancy_name.csv",
                new_value=None,
                exp_new_value=None,
                exp_new_get_value=None,
            ),
            id="file link with fileToKeyMap with payload that gets reset",
        ),
        pytest.param(
            *PortParams(
                port_cfg=create_valid_port_config(
                    "data:*/*",
                    key="some_file_on_datcore",
                    value={
                        "store": datcore_store_id(),
                        "path": f"{project_id()}/{node_uuid()}/{this_node_file_name().name}",
                        "dataset": "some blahblah",
                        "label": "some blahblah",
                    },
                ),
                exp_value_type=(Path, str),
                exp_value_converter=Path,
                exp_value=FileLink(
                    store=datcore_store_id(),
                    path=f"{project_id()}/{node_uuid()}/{this_node_file_name().name}",
                    dataset="some blahblah",
                    label="some blahblah",
                ),
                exp_get_value=download_file_folder_name()
                / "some_file_on_datcore"
                / this_node_file_name().name,
                new_value=this_node_file_name(),
                exp_new_value=FileLink(
                    store=simcore_store_id(),
                    path=f"{project_id()}/{node_uuid()}/{this_node_file_name().name}",
                    e_tag=e_tag(),
                ),
                exp_new_get_value=download_file_folder_name()
                / "some_file_on_datcore"
                / this_node_file_name().name,
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
                exp_get_value=download_file_folder_name()
                / "download_link"
                / this_node_file_name().name,
                new_value=this_node_file_name(),
                exp_new_value=FileLink(
                    store=simcore_store_id(),
                    path=f"{project_id()}/{node_uuid()}/{this_node_file_name().name}",
                    e_tag=e_tag(),
                ),
                exp_new_get_value=download_file_folder_name()
                / "download_link"
                / this_node_file_name().name,
            ),
            id="download link file type gets set back on store",
        ),
        pytest.param(
            *PortParams(
                port_cfg=create_valid_port_config(
                    "data:*/*",
                    key="download_link_with_file_to_key",
                    fileToKeyMap={
                        "a_cool_file_type.zip": "download_link_with_file_to_key"
                    },
                    value={
                        "downloadLink": "https://raw.githubusercontent.com/ITISFoundation/osparc-simcore/master/README.md"
                    },
                ),
                exp_value_type=(Path, str),
                exp_value_converter=Path,
                exp_value=DownloadLink(
                    downloadLink="https://raw.githubusercontent.com/ITISFoundation/osparc-simcore/master/README.md"
                ),
                exp_get_value=download_file_folder_name()
                / "download_link_with_file_to_key"
                / "a_cool_file_type.zip",
                new_value=this_node_file_name(),
                exp_new_value=FileLink(
                    store=simcore_store_id(),
                    path=f"{project_id()}/{node_uuid()}/{this_node_file_name().name}",
                    e_tag=e_tag(),
                ),
                exp_new_get_value=download_file_folder_name()
                / "download_link_with_file_to_key"
                / "a_cool_file_type.zip",
            ),
            id="download link file type with filetokeymap gets set back on store",
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
                exp_get_value=download_file_folder_name()
                / "file_port_link"
                / another_node_file_name().name,
                new_value=this_node_file_name(),
                exp_new_value=FileLink(
                    store=simcore_store_id(),
                    path=f"{project_id()}/{node_uuid()}/{this_node_file_name().name}",
                    e_tag=e_tag(),
                ),
                exp_new_get_value=download_file_folder_name()
                / "file_port_link"
                / this_node_file_name().name,
            ),
            id="file node link type gets set back on store",
        ),
        pytest.param(
            *PortParams(
                port_cfg=create_valid_port_config(
                    "data:*/*",
                    key="file_port_link_with_file_to_key_map",
                    fileToKeyMap={
                        "a_cool_file_type.zip": "file_port_link_with_file_to_key_map"
                    },
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
                exp_get_value=download_file_folder_name()
                / "file_port_link_with_file_to_key_map"
                / "a_cool_file_type.zip",
                new_value=this_node_file_name(),
                exp_new_value=FileLink(
                    store=simcore_store_id(),
                    path=f"{project_id()}/{node_uuid()}/{this_node_file_name().name}",
                    e_tag=e_tag(),
                ),
                exp_new_get_value=download_file_folder_name()
                / "file_port_link_with_file_to_key_map"
                / "a_cool_file_type.zip",
            ),
            id="file node link type with file to key map gets set back on store",
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
    common_fixtures: None,
    user_id: int,
    project_id: str,
    node_uuid: str,
    port_cfg: Dict[str, Any],
    exp_value_type: Type[Union[int, float, bool, str, Path]],
    exp_value_converter: Type[Union[int, float, bool, str, Path]],
    exp_value: Union[int, float, bool, str, Path, FileLink, DownloadLink, PortLink],
    exp_get_value: Union[int, float, bool, str, Path],
    new_value: Union[int, float, bool, str, Path],
    exp_new_value: Union[int, float, bool, str, Path, FileLink],
    exp_new_get_value: Union[int, float, bool, str, Path],
    another_node_file: Path,
):
    @dataclass
    class FakeNodePorts:
        user_id: int
        project_id: str
        node_uuid: str

        @staticmethod
        async def get(key):
            # this gets called when a node links to another node we return the get value but for files it needs to be a real one
            return (
                another_node_file
                if port_cfg["type"].startswith("data:")
                else exp_get_value
            )

        @classmethod
        async def _node_ports_creator_cb(cls, node_uuid: str) -> "FakeNodePorts":
            return cls(
                user_id=user_id,
                project_id=project_id,
                node_uuid=node_uuid,
            )

        @staticmethod
        async def save_to_db_cb(node_ports):
            return

    fake_node_ports = FakeNodePorts(
        user_id=user_id,
        project_id=project_id,
        node_uuid=node_uuid,
    )
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

    if isinstance(exp_get_value, Path):
        # if it's a file let's create one there already
        exp_get_value.parent.mkdir(parents=True, exist_ok=True)
        exp_get_value.touch()

    if exp_get_value is None:
        assert await port.get() == None
    else:
        assert await port.get() == exp_get_value
        if isinstance(exp_value, PortLink) and isinstance(exp_get_value, Path):
            # as the file is moved internally we need to re-create it or it fails
            another_node_file_name().touch(exist_ok=True)
        # it should work several times
        assert await port.get() == exp_get_value

    # set a new value
    await port.set(new_value)
    assert port.value == exp_new_value

    if isinstance(exp_new_get_value, Path):
        # if it's a file let's create one there already
        exp_new_get_value.parent.mkdir(parents=True, exist_ok=True)
        exp_new_get_value.touch()
    if exp_new_get_value is None:
        assert await port.get() == None
    else:
        assert await port.get() == exp_new_get_value
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
def test_invalid_port(common_fixtures: None, port_cfg: Dict[str, Any]):
    with pytest.raises(ValidationError):
        Port(**port_cfg)


@pytest.mark.parametrize(
    "port_cfg", [(create_valid_port_config("data:*/*", key="set_some_inexisting_file"))]
)
async def test_invalid_file_type_setter(
    common_fixtures: None, project_id: str, node_uuid: str, port_cfg: Dict[str, Any]
):
    port = Port(**port_cfg)
    # set a file that does not exist
    with pytest.raises(exceptions.InvalidItemTypeError):
        await port.set("some/dummy/file/name")

    # set a folder fails too
    with pytest.raises(exceptions.InvalidItemTypeError):
        await port.set(Path(__file__).parent)
