# pylint: disable=pointless-statement
# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=too-many-positional-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import filecmp
import os
import tempfile
from asyncio import gather
from collections.abc import Awaitable, Callable, Iterable
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import np_helpers
import pytest
import sqlalchemy as sa
from faker import Faker
from models_library.projects import ProjectIDStr
from models_library.projects_nodes_io import (
    BaseFileLink,
    DownloadLink,
    LocationID,
    NodeIDStr,
    SimcoreS3FileID,
)
from models_library.services_types import ServicePortKey
from pydantic import TypeAdapter
from pytest_mock import MockerFixture
from servicelib.progress_bar import ProgressBarData
from settings_library.r_clone import RCloneSettings
from simcore_sdk import node_ports_v2
from simcore_sdk.node_ports_common.exceptions import UnboundPortError
from simcore_sdk.node_ports_v2 import exceptions
from simcore_sdk.node_ports_v2.links import ItemConcreteValue, PortLink
from simcore_sdk.node_ports_v2.nodeports_v2 import Nodeports, OutputsCallbacks
from simcore_sdk.node_ports_v2.port import Port
from utils_port_v2 import CONSTANT_UUID

pytest_simcore_core_services_selection = [
    "migration",
    "postgres",
    "storage",
    "redis",
]

pytest_simcore_ops_services_selection = [
    "minio",
    "adminer",
]


async def _check_port_valid(
    ports: Nodeports,
    config_dict: dict,
    port_type: str,
    key_name: str,
    key: str | int,
):
    port: Port = (await getattr(ports, port_type))[key]
    assert isinstance(port, Port)

    assert port.key == key_name
    port_schema = config_dict["schema"][port_type][key_name]

    # check required values
    assert port.label == port_schema["label"]
    assert port.description == port_schema["description"]
    assert port.property_type == port_schema["type"]
    assert port.display_order == port_schema["displayOrder"]
    # check optional values
    if "defaultValue" in port_schema:
        assert port.default_value == port_schema["defaultValue"]
    else:
        assert port.default_value is None
    if "fileToKeyMap" in port_schema:
        assert port.file_to_key_map == port_schema["fileToKeyMap"]
    else:
        assert port.file_to_key_map is None
    if "widget" in port_schema:
        assert port.widget == port_schema["widget"]
    else:
        assert port.widget is None

    # check payload values
    port_values = config_dict[port_type]
    if key_name in port_values:
        if isinstance(port_values[key_name], dict):
            assert port.value
            assert isinstance(port.value, DownloadLink | PortLink | BaseFileLink)
            assert (
                port.value.model_dump(by_alias=True, exclude_unset=True)
                == port_values[key_name]
            )
        else:
            assert port.value == port_values[key_name]
    elif "defaultValue" in port_schema:
        assert port.value == port_schema["defaultValue"]
    else:
        assert port.value is None


async def _check_ports_valid(ports: Nodeports, config_dict: dict, port_type: str):
    port_schemas = config_dict["schema"][port_type]
    for key in port_schemas:
        # test using "key" name
        await _check_port_valid(ports, config_dict, port_type, key, key)
        # test using index
        key_index = list(port_schemas.keys()).index(key)
        await _check_port_valid(ports, config_dict, port_type, key, key_index)


async def check_config_valid(ports: Nodeports, config_dict: dict):
    await _check_ports_valid(ports, config_dict, "inputs")
    await _check_ports_valid(ports, config_dict, "outputs")


@pytest.fixture(scope="session")
def e_tag() -> str:
    return "123154654684321-1"


@pytest.fixture
def symlink_path(tmp_path: Path) -> Iterable[Path]:
    file_name: Path = tmp_path / f"test_file_{Path(__file__).name}"
    symlink_path = file_name
    assert not symlink_path.exists()
    file_path = file_name.parent / f"source_{file_name.name}"
    assert not file_path.exists()

    file_path.write_text("some dummy data")
    assert file_path.exists()

    if not symlink_path.exists():
        # using a relative symlink, only these are supported
        os.symlink(os.path.relpath(file_path, "."), symlink_path)
        assert symlink_path.exists()

    yield symlink_path

    if symlink_path.exists():
        symlink_path.unlink()


@pytest.fixture
def config_value_symlink_path(symlink_path: Path) -> dict[str, Any]:
    return {"store": 0, "path": symlink_path}


@pytest.fixture(params=[True, False])
async def option_r_clone_settings(
    request, r_clone_settings_factory: Awaitable[RCloneSettings]
) -> RCloneSettings | None:
    if request.param:
        return await r_clone_settings_factory
    return None


async def test_default_configuration(
    user_id: int,
    project_id: str,
    node_uuid: NodeIDStr,
    default_configuration: dict[str, Any],
    option_r_clone_settings: RCloneSettings | None,
):
    config_dict = default_configuration
    await check_config_valid(
        await node_ports_v2.ports(
            user_id=user_id,
            project_id=ProjectIDStr(project_id),
            node_uuid=node_uuid,
            r_clone_settings=option_r_clone_settings,
        ),
        config_dict,
    )


async def test_invalid_ports(
    user_id: int,
    project_id: str,
    node_uuid: NodeIDStr,
    create_special_configuration: Callable,
    option_r_clone_settings: RCloneSettings | None,
):
    config_dict, _, _ = create_special_configuration()
    PORTS = await node_ports_v2.ports(
        user_id=user_id,
        project_id=ProjectIDStr(project_id),
        node_uuid=node_uuid,
        r_clone_settings=option_r_clone_settings,
    )
    await check_config_valid(PORTS, config_dict)

    with pytest.raises(exceptions.UnboundPortError):
        (await PORTS.inputs)[0]

    with pytest.raises(exceptions.UnboundPortError):
        (await PORTS.outputs)[0]


@pytest.mark.parametrize(
    "item_type, item_value, item_pytype",
    [
        ("integer", 26, int),
        ("integer", 0, int),
        ("integer", -52, int),
        ("number", -746.4748, float),
        ("number", 0.0, float),
        ("number", 4566.11235, float),
        ("boolean", False, bool),
        ("boolean", True, bool),
        ("string", "test-string", str),
        ("string", "", str),
    ],
)
async def test_port_value_accessors(
    user_id: int,
    project_id: str,
    node_uuid: NodeIDStr,
    create_special_configuration: Callable,
    item_type: str,
    item_value: ItemConcreteValue,
    item_pytype: type,
    option_r_clone_settings: RCloneSettings | None,
):  # pylint: disable=W0613, W0621
    item_key = TypeAdapter(ServicePortKey).validate_python("some_key")
    config_dict, _, _ = create_special_configuration(
        inputs=[(item_key, item_type, item_value)],
        outputs=[(item_key, item_type, None)],
    )

    PORTS = await node_ports_v2.ports(
        user_id=user_id,
        project_id=ProjectIDStr(project_id),
        node_uuid=node_uuid,
        r_clone_settings=option_r_clone_settings,
    )
    await check_config_valid(PORTS, config_dict)

    assert isinstance(await (await PORTS.inputs)[item_key].get(), item_pytype)
    assert await (await PORTS.inputs)[item_key].get() == item_value
    assert await (await PORTS.outputs)[item_key].get() is None

    assert isinstance(await PORTS.get(item_key), item_pytype)
    assert await PORTS.get(item_key) == item_value

    await (await PORTS.outputs)[item_key].set(item_value)
    assert (await PORTS.outputs)[item_key].value == item_value
    assert isinstance(await (await PORTS.outputs)[item_key].get(), item_pytype)
    assert await (await PORTS.outputs)[item_key].get() == item_value


@pytest.mark.parametrize(
    "item_type, item_value, item_pytype, config_value",
    [
        ("data:*/*", __file__, Path, {"store": 0, "path": __file__}),
        ("data:text/*", __file__, Path, {"store": 0, "path": __file__}),
        ("data:text/py", __file__, Path, {"store": 0, "path": __file__}),
        ("data:text/py", "symlink_path", Path, "config_value_symlink_path"),
    ],
)
async def test_port_file_accessors(
    create_special_configuration: Callable,
    s3_simcore_location: LocationID,
    item_type: str,
    item_value: str,
    item_pytype: type,
    config_value: dict[str, str],
    user_id: int,
    project_id: str,
    node_uuid: NodeIDStr,
    e_tag: str,
    option_r_clone_settings: RCloneSettings | None,
    request: pytest.FixtureRequest,
    constant_uuid4: None,
):

    if item_value == "symlink_path":
        item_value = request.getfixturevalue("symlink_path")
    if config_value == "config_value_symlink_path":
        config_value = request.getfixturevalue("config_value_symlink_path")

    config_value["path"] = f"{project_id}/{node_uuid}/{Path(config_value['path']).name}"

    config_dict, _project_id, _node_uuid = create_special_configuration(
        inputs=[("in_1", item_type, config_value)],
        outputs=[("out_34", item_type, None)],
    )

    assert _project_id == project_id
    assert _node_uuid == node_uuid

    PORTS = await node_ports_v2.ports(
        user_id=user_id,
        project_id=ProjectIDStr(project_id),
        node_uuid=node_uuid,
        r_clone_settings=option_r_clone_settings,
    )
    await check_config_valid(PORTS, config_dict)
    assert (
        await (await PORTS.outputs)[
            TypeAdapter(ServicePortKey).validate_python("out_34")
        ].get()
        is None
    )  # check emptyness
    with pytest.raises(exceptions.S3InvalidPathError):
        await (await PORTS.inputs)[
            TypeAdapter(ServicePortKey).validate_python("in_1")
        ].get()

    # this triggers an upload to S3 + configuration change
    await (await PORTS.outputs)[
        TypeAdapter(ServicePortKey).validate_python("out_34")
    ].set(item_value)
    # this is the link to S3 storage
    value = (await PORTS.outputs)[
        TypeAdapter(ServicePortKey).validate_python("out_34")
    ].value
    assert isinstance(value, DownloadLink | PortLink | BaseFileLink)
    received_file_link = value.model_dump(by_alias=True, exclude_unset=True)
    assert received_file_link["store"] == s3_simcore_location
    assert (
        received_file_link["path"]
        == Path(
            f"{project_id}", f"{node_uuid}", "out_34", Path(item_value).name
        ).as_posix()
    )
    # the eTag is created by the S3 server
    assert received_file_link["eTag"]

    # this triggers a download from S3 to a location in /tempdir/simcorefiles/item_key
    assert isinstance(
        await (await PORTS.outputs)[
            TypeAdapter(ServicePortKey).validate_python("out_34")
        ].get(),
        item_pytype,
    )
    downloaded_file = await (await PORTS.outputs)[
        TypeAdapter(ServicePortKey).validate_python("out_34")
    ].get()
    assert isinstance(downloaded_file, Path)
    assert downloaded_file.exists()
    assert str(
        await (await PORTS.outputs)[
            TypeAdapter(ServicePortKey).validate_python("out_34")
        ].get()
    ).startswith(
        str(
            Path(
                tempfile.gettempdir(),
                "simcorefiles",
                f"{CONSTANT_UUID}",
                "out_34",
            )
        )
    )
    filecmp.clear_cache()
    assert filecmp.cmp(item_value, downloaded_file)


async def test_adding_new_ports(
    user_id: int,
    project_id: str,
    node_uuid: NodeIDStr,
    create_special_configuration: Callable,
    postgres_db: sa.engine.Engine,
    option_r_clone_settings: RCloneSettings | None,
):
    config_dict, project_id, node_uuid = create_special_configuration()
    PORTS = await node_ports_v2.ports(
        user_id=user_id,
        project_id=ProjectIDStr(project_id),
        node_uuid=node_uuid,
        r_clone_settings=option_r_clone_settings,
    )
    await check_config_valid(PORTS, config_dict)

    # replace the configuration now, add an input
    config_dict["schema"]["inputs"].update(
        {
            "in_15": {
                "label": "additional data",
                "description": "here some additional data",
                "displayOrder": 2,
                "type": "integer",
            }
        }
    )
    config_dict["inputs"].update({"in_15": 15})
    np_helpers.update_configuration(
        postgres_db, project_id, node_uuid, config_dict
    )  # pylint: disable=E1101
    await check_config_valid(PORTS, config_dict)

    # # replace the configuration now, add an output
    config_dict["schema"]["outputs"].update(
        {
            "out_15": {
                "label": "output data",
                "description": "a cool output",
                "displayOrder": 2,
                "type": "boolean",
            }
        }
    )
    np_helpers.update_configuration(
        postgres_db, project_id, node_uuid, config_dict
    )  # pylint: disable=E1101
    await check_config_valid(PORTS, config_dict)


async def test_removing_ports(
    user_id: int,
    project_id: str,
    node_uuid: NodeIDStr,
    create_special_configuration: Callable,
    postgres_db: sa.engine.Engine,
    option_r_clone_settings: RCloneSettings | None,
):
    config_dict, project_id, node_uuid = create_special_configuration(
        inputs=[("in_14", "integer", 15), ("in_17", "boolean", False)],
        outputs=[("out_123", "string", "blahblah"), ("out_2", "number", -12.3)],
    )  # pylint: disable=W0612
    PORTS = await node_ports_v2.ports(
        user_id=user_id,
        project_id=ProjectIDStr(project_id),
        node_uuid=node_uuid,
        r_clone_settings=option_r_clone_settings,
    )
    await check_config_valid(PORTS, config_dict)
    # let's remove the first input
    del config_dict["schema"]["inputs"]["in_14"]
    del config_dict["inputs"]["in_14"]
    np_helpers.update_configuration(
        postgres_db, project_id, node_uuid, config_dict
    )  # pylint: disable=E1101
    await check_config_valid(PORTS, config_dict)
    # let's do the same for the second output
    del config_dict["schema"]["outputs"]["out_2"]
    del config_dict["outputs"]["out_2"]
    np_helpers.update_configuration(
        postgres_db, project_id, node_uuid, config_dict
    )  # pylint: disable=E1101
    await check_config_valid(PORTS, config_dict)


@pytest.mark.parametrize(
    "item_type, item_value, item_pytype",
    [
        ("integer", 26, int),
        ("integer", 0, int),
        ("integer", -52, int),
        ("number", -746.4748, float),
        ("number", 0.0, float),
        ("number", 4566.11235, float),
        ("boolean", False, bool),
        ("boolean", True, bool),
        ("string", "test-string", str),
        ("string", "", str),
        # TODO: add here schema-like port
    ],
)
async def test_get_value_from_previous_node(
    user_id: int,
    project_id: str,
    node_uuid: NodeIDStr,
    create_2nodes_configuration: Callable,
    create_node_link: Callable,
    item_type: str,
    item_value: ItemConcreteValue,
    item_pytype: type,
    option_r_clone_settings: RCloneSettings | None,
):
    config_dict, _, _ = create_2nodes_configuration(
        prev_node_inputs=None,
        prev_node_outputs=[("output_int", item_type, item_value)],
        inputs=[("in_15", item_type, create_node_link("output_int"))],
        outputs=None,
        project_id=project_id,
        previous_node_id=f"{uuid4()}",
        node_id=node_uuid,
    )

    PORTS = await node_ports_v2.ports(
        user_id=user_id,
        project_id=ProjectIDStr(project_id),
        node_uuid=node_uuid,
        r_clone_settings=option_r_clone_settings,
    )

    await check_config_valid(PORTS, config_dict)
    input_value = await (await PORTS.inputs)[
        TypeAdapter(ServicePortKey).validate_python("in_15")
    ].get()
    assert isinstance(input_value, item_pytype)
    assert (
        await (await PORTS.inputs)[
            TypeAdapter(ServicePortKey).validate_python("in_15")
        ].get()
        == item_value
    )


@pytest.mark.parametrize(
    "item_type, item_value, item_pytype",
    [
        ("data:*/*", __file__, Path),
        ("data:text/*", __file__, Path),
        ("data:text/py", __file__, Path),
    ],
)
async def test_get_file_from_previous_node(
    create_2nodes_configuration: Callable,
    user_id: int,
    project_id: str,
    node_uuid: NodeIDStr,
    create_node_link: Callable,
    create_store_link: Callable,
    item_type: str,
    item_value: str,
    item_pytype: type,
    option_r_clone_settings: RCloneSettings | None,
    constant_uuid4: None,
):
    config_dict, _, _ = create_2nodes_configuration(
        prev_node_inputs=None,
        prev_node_outputs=[
            ("output_int", item_type, await create_store_link(item_value))
        ],
        inputs=[("in_15", item_type, create_node_link("output_int"))],
        outputs=None,
        project_id=project_id,
        previous_node_id=f"{uuid4()}",
        node_id=node_uuid,
    )
    PORTS = await node_ports_v2.ports(
        user_id=user_id,
        project_id=ProjectIDStr(project_id),
        node_uuid=node_uuid,
        r_clone_settings=option_r_clone_settings,
    )
    await check_config_valid(PORTS, config_dict)
    file_path = await (await PORTS.inputs)[
        TypeAdapter(ServicePortKey).validate_python("in_15")
    ].get()
    assert isinstance(file_path, item_pytype)
    assert file_path == Path(
        tempfile.gettempdir(),
        "simcorefiles",
        f"{CONSTANT_UUID}",
        "in_15",
        Path(item_value).name,
    )
    assert isinstance(file_path, Path)
    assert file_path.exists()
    filecmp.clear_cache()
    assert filecmp.cmp(file_path, item_value)


@pytest.mark.parametrize(
    "item_type, item_value, item_alias, item_pytype",
    [
        ("data:*/*", __file__, Path(__file__).name, Path),
        ("data:*/*", __file__, "some funky name.txt", Path),
        ("data:text/*", __file__, "some funky name without extension", Path),
        ("data:text/py", __file__, "öä$äö2-34 name without extension", Path),
    ],
)
async def test_get_file_from_previous_node_with_mapping_of_same_key_name(
    create_2nodes_configuration: Callable,
    user_id: int,
    project_id: str,
    node_uuid: NodeIDStr,
    create_node_link: Callable,
    create_store_link: Callable,
    postgres_db: sa.engine.Engine,
    item_type: str,
    item_value: str,
    item_alias: str,
    item_pytype: type,
    option_r_clone_settings: RCloneSettings | None,
    constant_uuid4: None,
):
    config_dict, _, this_node_uuid = create_2nodes_configuration(
        prev_node_inputs=None,
        prev_node_outputs=[("in_15", item_type, await create_store_link(item_value))],
        inputs=[("in_15", item_type, create_node_link("in_15"))],
        outputs=None,
        project_id=project_id,
        previous_node_id=f"{uuid4()}",
        node_id=node_uuid,
    )
    PORTS = await node_ports_v2.ports(
        user_id=user_id,
        project_id=ProjectIDStr(project_id),
        node_uuid=node_uuid,
        r_clone_settings=option_r_clone_settings,
    )
    await check_config_valid(PORTS, config_dict)
    # add a filetokeymap
    config_dict["schema"]["inputs"]["in_15"]["fileToKeyMap"] = {item_alias: "in_15"}
    np_helpers.update_configuration(
        postgres_db, project_id, this_node_uuid, config_dict
    )  # pylint: disable=E1101
    await check_config_valid(PORTS, config_dict)
    file_path = await (await PORTS.inputs)[
        TypeAdapter(ServicePortKey).validate_python("in_15")
    ].get()
    assert isinstance(file_path, item_pytype)
    assert file_path == Path(
        tempfile.gettempdir(),
        "simcorefiles",
        f"{CONSTANT_UUID}",
        "in_15",
        item_alias,
    )
    assert isinstance(file_path, Path)
    assert file_path.exists()
    filecmp.clear_cache()
    assert filecmp.cmp(file_path, item_value)


@pytest.mark.parametrize(
    "item_type, item_value, item_alias, item_pytype",
    [
        ("data:*/*", __file__, Path(__file__).name, Path),
        ("data:*/*", __file__, "some funky name.txt", Path),
        ("data:text/*", __file__, "some funky name without extension", Path),
        ("data:text/py", __file__, "öä$äö2-34 name without extension", Path),
    ],
)
async def test_file_mapping(
    create_special_configuration: Callable,
    user_id: int,
    project_id: str,
    node_uuid: NodeIDStr,
    s3_simcore_location: LocationID,
    create_store_link: Callable,
    postgres_db: sa.engine.Engine,
    item_type: str,
    item_value: str,
    item_alias: str,
    item_pytype: type,
    option_r_clone_settings: RCloneSettings | None,
    create_valid_file_uuid: Callable[[str, Path], SimcoreS3FileID],
    constant_uuid4: None,
):
    config_dict, project_id, node_uuid = create_special_configuration(
        inputs=[("in_1", item_type, await create_store_link(item_value))],
        outputs=[("out_1", item_type, None)],
        project_id=project_id,
        node_id=node_uuid,
    )
    PORTS = await node_ports_v2.ports(
        user_id=user_id,
        project_id=ProjectIDStr(project_id),
        node_uuid=node_uuid,
        r_clone_settings=option_r_clone_settings,
    )
    await check_config_valid(PORTS, config_dict)
    # add a filetokeymap
    config_dict["schema"]["inputs"]["in_1"]["fileToKeyMap"] = {item_alias: "in_1"}
    config_dict["schema"]["outputs"]["out_1"]["fileToKeyMap"] = {item_alias: "out_1"}
    np_helpers.update_configuration(
        postgres_db, project_id, node_uuid, config_dict
    )  # pylint: disable=E1101
    await check_config_valid(PORTS, config_dict)
    file_path = await (await PORTS.inputs)[
        TypeAdapter(ServicePortKey).validate_python("in_1")
    ].get()
    assert isinstance(file_path, item_pytype)
    assert file_path == Path(
        tempfile.gettempdir(),
        "simcorefiles",
        f"{CONSTANT_UUID}",
        "in_1",
        item_alias,
    )

    # let's get it a second time to see if replacing works
    file_path = await (await PORTS.inputs)[
        TypeAdapter(ServicePortKey).validate_python("in_1")
    ].get()
    assert isinstance(file_path, item_pytype)
    assert file_path == Path(
        tempfile.gettempdir(),
        "simcorefiles",
        f"{CONSTANT_UUID}",
        "in_1",
        item_alias,
    )

    # now set
    invalid_alias = Path("invalid_alias.fjfj")
    with pytest.raises(exceptions.PortNotFound):
        await PORTS.set_file_by_keymap(invalid_alias)
    assert isinstance(file_path, Path)
    await PORTS.set_file_by_keymap(file_path)
    file_id = create_valid_file_uuid("out_1", file_path)
    value = (await PORTS.outputs)[
        TypeAdapter(ServicePortKey).validate_python("out_1")
    ].value
    assert isinstance(value, DownloadLink | PortLink | BaseFileLink)
    received_file_link = value.model_dump(by_alias=True, exclude_unset=True)
    assert received_file_link["store"] == s3_simcore_location
    assert received_file_link["path"] == file_id
    # received a new eTag
    assert received_file_link["eTag"]


@pytest.fixture
def int_item_value() -> int:
    return 42


@pytest.fixture
def parallel_int_item_value() -> int:
    return 142


@pytest.fixture
def port_count() -> int:
    # the issue manifests from 4 ports onwards
    # going for many more ports to be sure issue
    # always occurs in CI or locally
    return 20


async def test_regression_concurrent_port_update_fails(
    user_id: int,
    project_id: str,
    node_uuid: NodeIDStr,
    create_special_configuration: Callable,
    int_item_value: int,
    parallel_int_item_value: int,
    port_count: int,
    option_r_clone_settings: RCloneSettings | None,
) -> None:
    """
    when using `await PORTS.outputs` test will fail
    an unexpected status will end up in the database
    """

    outputs = [(f"value_{i}", "integer", None) for i in range(port_count)]
    config_dict, _, _ = create_special_configuration(inputs=[], outputs=outputs)

    PORTS = await node_ports_v2.ports(
        user_id=user_id,
        project_id=ProjectIDStr(project_id),
        node_uuid=node_uuid,
        r_clone_settings=option_r_clone_settings,
    )
    await check_config_valid(PORTS, config_dict)

    # when writing in serial these are expected to work
    for item_key, _, _ in outputs:
        await (await PORTS.outputs)[
            TypeAdapter(ServicePortKey).validate_python(item_key)
        ].set(int_item_value)
        assert (await PORTS.outputs)[
            TypeAdapter(ServicePortKey).validate_python(item_key)
        ].value == int_item_value

    # when writing in parallel and reading back,
    # they fail, with enough concurrency
    async def _upload_create_task(item_key: str) -> None:
        await (await PORTS.outputs)[
            TypeAdapter(ServicePortKey).validate_python(item_key)
        ].set(parallel_int_item_value)

    # updating in parallel creates a race condition
    results = await gather(
        *[_upload_create_task(item_key) for item_key, _, _ in outputs]
    )
    assert len(results) == port_count

    # since a race condition was created when uploading values in parallel
    # it is expected to find at least one mismatching value here
    with pytest.raises(AssertionError) as exc_info:  # noqa: PT012
        for item_key, _, _ in outputs:
            assert (await PORTS.outputs)[
                TypeAdapter(ServicePortKey).validate_python(item_key)
            ].value == parallel_int_item_value

    assert exc_info.value.args[0].startswith(
        f"assert {int_item_value} == {parallel_int_item_value}\n +  where {int_item_value} = Port("
    )


class _Callbacks(OutputsCallbacks):
    async def aborted(self, key: ServicePortKey) -> None:
        pass

    async def finished_succesfully(self, key: ServicePortKey) -> None:
        pass

    async def finished_with_error(self, key: ServicePortKey) -> None:
        pass


@pytest.fixture
async def output_callbacks() -> _Callbacks:
    return _Callbacks()


@pytest.fixture
async def spy_outputs_callbaks(
    mocker: MockerFixture, output_callbacks: _Callbacks
) -> dict[str, AsyncMock]:
    return {
        "aborted": mocker.spy(output_callbacks, "aborted"),
        "finished_succesfully": mocker.spy(output_callbacks, "finished_succesfully"),
        "finished_with_error": mocker.spy(output_callbacks, "finished_with_error"),
    }


@pytest.mark.parametrize("use_output_callbacks", [True, False])
async def test_batch_update_inputs_outputs(
    user_id: int,
    project_id: str,
    node_uuid: NodeIDStr,
    create_special_configuration: Callable,
    port_count: int,
    option_r_clone_settings: RCloneSettings | None,
    faker: Faker,
    output_callbacks: _Callbacks,
    spy_outputs_callbaks: dict[str, AsyncMock],
    use_output_callbacks: bool,
) -> None:
    callbacks = output_callbacks if use_output_callbacks else None

    outputs = [(f"value_out_{i}", "integer", None) for i in range(port_count)]
    inputs = [(f"value_in_{i}", "integer", None) for i in range(port_count)]
    config_dict, _, _ = create_special_configuration(inputs=inputs, outputs=outputs)

    PORTS = await node_ports_v2.ports(
        user_id=user_id,
        project_id=ProjectIDStr(project_id),
        node_uuid=node_uuid,
        r_clone_settings=option_r_clone_settings,
    )
    await check_config_valid(PORTS, config_dict)

    async with ProgressBarData(num_steps=2, description=faker.pystr()) as progress_bar:
        port_values = (await PORTS.outputs).values()
        await PORTS.set_multiple(
            {
                TypeAdapter(ServicePortKey).validate_python(port.key): (k, None)
                for k, port in enumerate(port_values)
            },
            progress_bar=progress_bar,
            outputs_callbacks=callbacks,
        )
        assert len(spy_outputs_callbaks["finished_succesfully"].call_args_list) == (
            len(port_values) if use_output_callbacks else 0
        )
        # pylint: disable=protected-access
        assert progress_bar._current_steps == pytest.approx(1)  # noqa: SLF001
        await PORTS.set_multiple(
            {
                TypeAdapter(ServicePortKey).validate_python(port.key): (k, None)
                for k, port in enumerate((await PORTS.inputs).values(), start=1000)
            },
            progress_bar=progress_bar,
            outputs_callbacks=callbacks,
        )
        # inputs do not trigger callbacks
        assert len(spy_outputs_callbaks["finished_succesfully"].call_args_list) == (
            len(port_values) if use_output_callbacks else 0
        )
        assert progress_bar._current_steps == pytest.approx(2)  # noqa: SLF001

    ports_outputs = await PORTS.outputs
    ports_inputs = await PORTS.inputs
    for k, asd in enumerate(outputs):
        item_key, _, _ = asd
        assert (
            ports_outputs[TypeAdapter(ServicePortKey).validate_python(item_key)].value
            == k
        )
        assert (
            await ports_outputs[
                TypeAdapter(ServicePortKey).validate_python(item_key)
            ].get()
            == k
        )

    for k, asd in enumerate(inputs, start=1000):
        item_key, _, _ = asd
        assert (
            ports_inputs[TypeAdapter(ServicePortKey).validate_python(item_key)].value
            == k
        )
        assert (
            await ports_inputs[
                TypeAdapter(ServicePortKey).validate_python(item_key)
            ].get()
            == k
        )

    # test missing key raises error
    async with ProgressBarData(num_steps=1, description=faker.pystr()) as progress_bar:
        with pytest.raises(UnboundPortError):
            await PORTS.set_multiple(
                {
                    TypeAdapter(ServicePortKey).validate_python(
                        "missing_key_in_both"
                    ): (123132, None)
                },
                progress_bar=progress_bar,
                outputs_callbacks=callbacks,
            )

    assert len(spy_outputs_callbaks["finished_succesfully"].call_args_list) == (
        len(port_values) if use_output_callbacks else 0
    )
    assert len(spy_outputs_callbaks["aborted"].call_args_list) == 0
    assert len(spy_outputs_callbaks["finished_with_error"].call_args_list) == 0
