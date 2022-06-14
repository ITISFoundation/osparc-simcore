# pylint: disable=pointless-statement
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import filecmp
import os
import tempfile
import threading
from asyncio import gather
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, Iterable, Optional, Type, Union
from uuid import uuid4

import np_helpers
import pytest
import sqlalchemy as sa
from models_library.projects_nodes_io import LocationID
from settings_library.r_clone import RCloneSettings
from simcore_sdk import node_ports_v2
from simcore_sdk.node_ports_common.exceptions import UnboundPortError
from simcore_sdk.node_ports_v2 import exceptions
from simcore_sdk.node_ports_v2.links import ItemConcreteValue
from simcore_sdk.node_ports_v2.nodeports_v2 import Nodeports
from simcore_sdk.node_ports_v2.port import Port

pytest_simcore_core_services_selection = [
    "migration",
    "postgres",
    "storage",
]

pytest_simcore_ops_services_selection = [
    "minio",
    "adminer",
]


async def _check_port_valid(
    ports: Nodeports,
    config_dict: Dict,
    port_type: str,
    key_name: str,
    key: Union[str, int],
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
        assert port.default_value == None
    if "fileToKeyMap" in port_schema:
        assert port.file_to_key_map == port_schema["fileToKeyMap"]
    else:
        assert port.file_to_key_map == None
    if "widget" in port_schema:
        assert port.widget == port_schema["widget"]
    else:
        assert port.widget == None

    # check payload values
    port_values = config_dict[port_type]
    if key_name in port_values:
        if isinstance(port_values[key_name], dict):
            assert (
                port.value.dict(by_alias=True, exclude_unset=True)
                == port_values[key_name]
            )
        else:
            assert port.value == port_values[key_name]
    elif "defaultValue" in port_schema:
        assert port.value == port_schema["defaultValue"]
    else:
        assert port.value == None


async def _check_ports_valid(ports: Nodeports, config_dict: Dict, port_type: str):
    port_schemas = config_dict["schema"][port_type]
    for key in port_schemas.keys():
        # test using "key" name
        await _check_port_valid(ports, config_dict, port_type, key, key)
        # test using index
        key_index = list(port_schemas.keys()).index(key)
        await _check_port_valid(ports, config_dict, port_type, key, key_index)


async def check_config_valid(ports: Nodeports, config_dict: Dict):
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
def config_value_symlink_path(symlink_path: Path) -> Dict[str, Any]:
    return {"store": 0, "path": symlink_path}


@pytest.fixture(params=[True, False])
async def option_r_clone_settings(
    request, r_clone_settings_factory: Awaitable[RCloneSettings]
) -> Optional[RCloneSettings]:
    if request.param:
        return await r_clone_settings_factory
    return None


async def test_default_configuration(
    user_id: int,
    project_id: str,
    node_uuid: str,
    default_configuration: Dict[str, Any],
    option_r_clone_settings: Optional[RCloneSettings],
):
    config_dict = default_configuration
    await check_config_valid(
        await node_ports_v2.ports(
            user_id=user_id,
            project_id=project_id,
            node_uuid=node_uuid,
            r_clone_settings=option_r_clone_settings,
        ),
        config_dict,
    )


async def test_invalid_ports(
    user_id: int,
    project_id: str,
    node_uuid: str,
    create_special_configuration: Callable,
    option_r_clone_settings: Optional[RCloneSettings],
):
    config_dict, _, _ = create_special_configuration()
    PORTS = await node_ports_v2.ports(
        user_id=user_id,
        project_id=project_id,
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
    node_uuid: str,
    create_special_configuration: Callable,
    item_type: str,
    item_value: ItemConcreteValue,
    item_pytype: Type,
    option_r_clone_settings: Optional[RCloneSettings],
):  # pylint: disable=W0613, W0621
    item_key = "some_key"
    config_dict, _, _ = create_special_configuration(
        inputs=[(item_key, item_type, item_value)],
        outputs=[(item_key, item_type, None)],
    )

    PORTS = await node_ports_v2.ports(
        user_id=user_id,
        project_id=project_id,
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
        (
            "data:text/py",
            pytest.lazy_fixture("symlink_path"),
            Path,
            pytest.lazy_fixture("config_value_symlink_path"),
        ),
    ],
)
async def test_port_file_accessors(
    create_special_configuration: Callable,
    filemanager_cfg: None,
    s3_simcore_location: LocationID,
    bucket: str,
    item_type: str,
    item_value: str,
    item_pytype: Type,
    config_value: Dict[str, str],
    user_id: int,
    project_id: str,
    node_uuid: str,
    e_tag: str,
    option_r_clone_settings: Optional[RCloneSettings],
):  # pylint: disable=W0613, W0621

    config_value["path"] = f"{project_id}/{node_uuid}/{Path(config_value['path']).name}"

    config_dict, _project_id, _node_uuid = create_special_configuration(
        inputs=[("in_1", item_type, config_value)],
        outputs=[("out_34", item_type, None)],
    )

    assert _project_id == project_id
    assert _node_uuid == node_uuid

    PORTS = await node_ports_v2.ports(
        user_id=user_id,
        project_id=project_id,
        node_uuid=node_uuid,
        r_clone_settings=option_r_clone_settings,
    )
    await check_config_valid(PORTS, config_dict)
    assert await (await PORTS.outputs)["out_34"].get() is None  # check emptyness
    with pytest.raises(exceptions.S3InvalidPathError):
        await (await PORTS.inputs)["in_1"].get()

    # this triggers an upload to S3 + configuration change
    await (await PORTS.outputs)["out_34"].set(item_value)
    # this is the link to S3 storage
    received_file_link = (await PORTS.outputs)["out_34"].value.dict(
        by_alias=True, exclude_unset=True
    )
    assert received_file_link["store"] == s3_simcore_location
    assert (
        received_file_link["path"]
        == Path(f"{project_id}", f"{node_uuid}", Path(item_value).name).as_posix()
    )
    # the eTag is created by the S3 server
    assert received_file_link["eTag"]

    # this triggers a download from S3 to a location in /tempdir/simcorefiles/item_key
    assert isinstance(await (await PORTS.outputs)["out_34"].get(), item_pytype)
    downloaded_file = await (await PORTS.outputs)["out_34"].get()
    assert isinstance(downloaded_file, Path)
    assert downloaded_file.exists()
    assert str(await (await PORTS.outputs)["out_34"].get()).startswith(
        str(
            Path(
                tempfile.gettempdir(),
                "simcorefiles",
                f"{threading.get_ident()}",
                "out_34",
            )
        )
    )
    filecmp.clear_cache()
    assert filecmp.cmp(item_value, downloaded_file)


async def test_adding_new_ports(
    user_id: int,
    project_id: str,
    node_uuid: str,
    create_special_configuration: Callable,
    postgres_db: sa.engine.Engine,
    option_r_clone_settings: Optional[RCloneSettings],
):
    config_dict, project_id, node_uuid = create_special_configuration()
    PORTS = await node_ports_v2.ports(
        user_id=user_id,
        project_id=project_id,
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
    node_uuid: str,
    create_special_configuration: Callable,
    postgres_db: sa.engine.Engine,
    option_r_clone_settings: Optional[RCloneSettings],
):
    config_dict, project_id, node_uuid = create_special_configuration(
        inputs=[("in_14", "integer", 15), ("in_17", "boolean", False)],
        outputs=[("out_123", "string", "blahblah"), ("out_2", "number", -12.3)],
    )  # pylint: disable=W0612
    PORTS = await node_ports_v2.ports(
        user_id=user_id,
        project_id=project_id,
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
    node_uuid: str,
    create_2nodes_configuration: Callable,
    create_node_link: Callable,
    item_type: str,
    item_value: ItemConcreteValue,
    item_pytype: Type,
    option_r_clone_settings: Optional[RCloneSettings],
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
        project_id=project_id,
        node_uuid=node_uuid,
        r_clone_settings=option_r_clone_settings,
    )

    await check_config_valid(PORTS, config_dict)
    input_value = await (await PORTS.inputs)["in_15"].get()
    assert isinstance(input_value, item_pytype)
    assert await (await PORTS.inputs)["in_15"].get() == item_value


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
    node_uuid: str,
    filemanager_cfg: None,
    create_node_link: Callable,
    create_store_link: Callable,
    item_type: str,
    item_value: str,
    item_pytype: Type,
    option_r_clone_settings: Optional[RCloneSettings],
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
        project_id=project_id,
        node_uuid=node_uuid,
        r_clone_settings=option_r_clone_settings,
    )
    await check_config_valid(PORTS, config_dict)
    file_path = await (await PORTS.inputs)["in_15"].get()
    assert isinstance(file_path, item_pytype)
    assert file_path == Path(
        tempfile.gettempdir(),
        "simcorefiles",
        f"{threading.get_ident()}",
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
    node_uuid: str,
    filemanager_cfg: None,
    create_node_link: Callable,
    create_store_link: Callable,
    postgres_db: sa.engine.Engine,
    item_type: str,
    item_value: str,
    item_alias: str,
    item_pytype: Type,
    option_r_clone_settings: Optional[RCloneSettings],
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
        project_id=project_id,
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
    file_path = await (await PORTS.inputs)["in_15"].get()
    assert isinstance(file_path, item_pytype)
    assert file_path == Path(
        tempfile.gettempdir(),
        "simcorefiles",
        f"{threading.get_ident()}",
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
    node_uuid: str,
    filemanager_cfg: None,
    s3_simcore_location: LocationID,
    bucket: str,
    create_store_link: Callable,
    postgres_db: sa.engine.Engine,
    item_type: str,
    item_value: str,
    item_alias: str,
    item_pytype: Type,
    option_r_clone_settings: Optional[RCloneSettings],
):
    config_dict, project_id, node_uuid = create_special_configuration(
        inputs=[("in_1", item_type, await create_store_link(item_value))],
        outputs=[("out_1", item_type, None)],
        project_id=project_id,
        node_id=node_uuid,
    )
    PORTS = await node_ports_v2.ports(
        user_id=user_id,
        project_id=project_id,
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
    file_path = await (await PORTS.inputs)["in_1"].get()
    assert isinstance(file_path, item_pytype)
    assert file_path == Path(
        tempfile.gettempdir(),
        "simcorefiles",
        f"{threading.get_ident()}",
        "in_1",
        item_alias,
    )

    # let's get it a second time to see if replacing works
    file_path = await (await PORTS.inputs)["in_1"].get()
    assert isinstance(file_path, item_pytype)
    assert file_path == Path(
        tempfile.gettempdir(),
        "simcorefiles",
        f"{threading.get_ident()}",
        "in_1",
        item_alias,
    )

    # now set
    invalid_alias = Path("invalid_alias.fjfj")
    with pytest.raises(exceptions.PortNotFound):
        await PORTS.set_file_by_keymap(invalid_alias)
    assert isinstance(file_path, Path)
    await PORTS.set_file_by_keymap(file_path)
    file_id = np_helpers.file_uuid(file_path, project_id, node_uuid)
    received_file_link = (await PORTS.outputs)["out_1"].value.dict(
        by_alias=True, exclude_unset=True
    )
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
    node_uuid: str,
    create_special_configuration: Callable,
    int_item_value: int,
    parallel_int_item_value: int,
    port_count: int,
    option_r_clone_settings: Optional[RCloneSettings],
) -> None:
    """
    when using `await PORTS.outputs` test will fail
    an unexpected status will end up in the database
    """

    outputs = [(f"value_{i}", "integer", None) for i in range(port_count)]
    config_dict, _, _ = create_special_configuration(inputs=[], outputs=outputs)

    PORTS = await node_ports_v2.ports(
        user_id=user_id,
        project_id=project_id,
        node_uuid=node_uuid,
        r_clone_settings=option_r_clone_settings,
    )
    await check_config_valid(PORTS, config_dict)

    # when writing in serial these are expected to work
    for item_key, _, _ in outputs:
        await (await PORTS.outputs)[item_key].set(int_item_value)
        assert (await PORTS.outputs)[item_key].value == int_item_value

    # when writing in parallel and reading back,
    # they fail, with enough concurrency
    async def _upload_create_task(item_key: str) -> None:
        await (await PORTS.outputs)[item_key].set(parallel_int_item_value)

    # updating in parallel creates a race condition
    results = await gather(
        *[_upload_create_task(item_key) for item_key, _, _ in outputs]
    )
    assert len(results) == port_count

    # since a race condition was created when uploading values in parallel
    # it is expected to find at least one mismatching value here
    with pytest.raises(AssertionError) as exc_info:
        for item_key, _, _ in outputs:
            assert (await PORTS.outputs)[item_key].value == parallel_int_item_value

    assert exc_info.value.args[0].startswith(
        f"assert {int_item_value} == {parallel_int_item_value}\n +  where {int_item_value} = Port("
    )


async def test_batch_update_inputs_outputs(
    user_id: int,
    project_id: str,
    node_uuid: str,
    create_special_configuration: Callable,
    port_count: int,
    option_r_clone_settings: Optional[RCloneSettings],
) -> None:
    outputs = [(f"value_out_{i}", "integer", None) for i in range(port_count)]
    inputs = [(f"value_in_{i}", "integer", None) for i in range(port_count)]
    config_dict, _, _ = create_special_configuration(inputs=inputs, outputs=outputs)

    PORTS = await node_ports_v2.ports(
        user_id=user_id,
        project_id=project_id,
        node_uuid=node_uuid,
        r_clone_settings=option_r_clone_settings,
    )
    await check_config_valid(PORTS, config_dict)

    await PORTS.set_multiple(
        {port.key: k for k, port in enumerate((await PORTS.outputs).values())}
    )
    await PORTS.set_multiple(
        {
            port.key: k
            for k, port in enumerate((await PORTS.inputs).values(), start=1000)
        }
    )

    ports_outputs = await PORTS.outputs
    ports_inputs = await PORTS.inputs
    for k, asd in enumerate(outputs):
        item_key, _, _ = asd
        assert ports_outputs[item_key].value == k
        assert await ports_outputs[item_key].get() == k

    for k, asd in enumerate(inputs, start=1000):
        item_key, _, _ = asd
        assert ports_inputs[item_key].value == k
        assert await ports_inputs[item_key].get() == k

    # test missing key raises error
    with pytest.raises(UnboundPortError):
        await PORTS.set_multiple({"missing_key_in_both": 123132})
