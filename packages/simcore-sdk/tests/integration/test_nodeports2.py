# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=too-many-arguments
# pylint:disable=pointless-statement

import filecmp
import tempfile
from pathlib import Path
from typing import Callable, Dict, Type

import np_helpers  # pylint: disable=no-name-in-module
import pytest
import sqlalchemy as sa
from simcore_sdk import node_ports_v2
from simcore_sdk.node_ports import exceptions
from simcore_sdk.node_ports_v2.links import ItemConcreteValue
from simcore_sdk.node_ports_v2.nodeports_v2 import Nodeports

core_services = ["postgres", "storage"]

ops_services = ["minio"]


async def _check_port_valid(
    ports: Nodeports, config_dict: Dict, port_type: str, key_name: str, key: str
):
    assert (await getattr(ports, port_type))[key].key == key_name
    # check required values
    assert (await getattr(ports, port_type))[key].label == config_dict["schema"][
        port_type
    ][key_name]["label"]
    assert (await getattr(ports, port_type))[key].description == config_dict["schema"][
        port_type
    ][key_name]["description"]
    assert (await getattr(ports, port_type))[key].property_type == config_dict[
        "schema"
    ][port_type][key_name]["type"]
    assert (await getattr(ports, port_type))[key].display_order == config_dict[
        "schema"
    ][port_type][key_name]["displayOrder"]
    # check optional values
    if "defaultValue" in config_dict["schema"][port_type][key_name]:
        assert (await getattr(ports, port_type))[key].default_value == config_dict[
            "schema"
        ][port_type][key_name]["defaultValue"]
    else:
        assert (await getattr(ports, port_type))[key].default_value == None
    if "fileToKeyMap" in config_dict["schema"][port_type][key_name]:
        assert (await getattr(ports, port_type))[key].file_to_key_map == config_dict[
            "schema"
        ][port_type][key_name]["fileToKeyMap"]
    else:
        assert (await getattr(ports, port_type))[key].file_to_key_map == None
    if "widget" in config_dict["schema"][port_type][key_name]:
        assert (await getattr(ports, port_type))[key].widget == config_dict["schema"][
            port_type
        ][key_name]["widget"]
    else:
        assert (await getattr(ports, port_type))[key].widget == None
    # check payload values
    if key_name in config_dict[port_type]:
        if isinstance(config_dict[port_type][key_name], dict):
            assert (await getattr(ports, port_type))[key].value.dict(
                by_alias=True, exclude_unset=True
            ) == config_dict[port_type][key_name]
        else:
            assert (await getattr(ports, port_type))[key].value == config_dict[
                port_type
            ][key_name]
    elif "defaultValue" in config_dict["schema"][port_type][key_name]:
        assert (await getattr(ports, port_type))[key].value == config_dict["schema"][
            port_type
        ][key_name]["defaultValue"]
    else:
        assert (await getattr(ports, port_type))[key].value == None


async def _check_ports_valid(ports: Nodeports, config_dict: Dict, port_type: str):
    for key in config_dict["schema"][port_type].keys():
        # test using "key" name
        await _check_port_valid(ports, config_dict, port_type, key, key)
        # test using index
        key_index = list(config_dict["schema"][port_type].keys()).index(key)
        await _check_port_valid(ports, config_dict, port_type, key, key_index)


async def check_config_valid(ports: Nodeports, config_dict: Dict):
    await _check_ports_valid(ports, config_dict, "inputs")
    await _check_ports_valid(ports, config_dict, "outputs")


@pytest.fixture(scope="session")
def e_tag() -> str:
    return "123154654684321-1"


async def test_default_configuration(
    default_configuration: Dict,
):  # pylint: disable=W0613, W0621
    config_dict = default_configuration
    await check_config_valid(await node_ports_v2.ports(), config_dict)


async def test_invalid_ports(special_configuration: Callable):
    config_dict, _, _ = special_configuration()
    PORTS = await node_ports_v2.ports()
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
    special_configuration: Callable,
    item_type: str,
    item_value: ItemConcreteValue,
    item_pytype: Type,
):  # pylint: disable=W0613, W0621
    item_key = "some_key"
    config_dict, _, _ = special_configuration(
        inputs=[(item_key, item_type, item_value)],
        outputs=[(item_key, item_type, None)],
    )

    PORTS = await node_ports_v2.ports()
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
        ("data:*/*", __file__, Path, {"store": "0", "path": __file__}),
        ("data:text/*", __file__, Path, {"store": "0", "path": __file__}),
        ("data:text/py", __file__, Path, {"store": "0", "path": __file__}),
    ],
)
async def test_port_file_accessors(
    special_configuration: Callable,
    filemanager_cfg: None,
    s3_simcore_location: str,
    bucket: str,
    item_type: str,
    item_value: str,
    item_pytype: Type,
    config_value: Dict[str, str],
    e_tag: str,
):  # pylint: disable=W0613, W0621
    config_dict, project_id, node_uuid = special_configuration(
        inputs=[("in_1", item_type, config_value)],
        outputs=[("out_34", item_type, None)],
    )
    PORTS = await node_ports_v2.ports()
    await check_config_valid(PORTS, config_dict)
    assert await (await PORTS.outputs)["out_34"].get() is None  # check emptyness
    # with pytest.raises(exceptions.S3InvalidPathError):
    #     await PORTS.inputs["in_1"].get()

    # this triggers an upload to S3 + configuration change
    await (await PORTS.outputs)["out_34"].set(item_value)
    # this is the link to S3 storage
    received_file_link = (await PORTS.outputs)["out_34"].value.dict(
        by_alias=True, exclude_unset=True
    )
    assert received_file_link["store"] == s3_simcore_location
    assert (
        received_file_link["path"]
        == Path(str(project_id), str(node_uuid), Path(item_value).name).as_posix()
    )
    # the eTag is created by the S3 server
    assert received_file_link["eTag"]

    # this triggers a download from S3 to a location in /tempdir/simcorefiles/item_key
    assert isinstance(await (await PORTS.outputs)["out_34"].get(), item_pytype)
    assert (await (await PORTS.outputs)["out_34"].get()).exists()
    assert str(await (await PORTS.outputs)["out_34"].get()).startswith(
        str(Path(tempfile.gettempdir(), "simcorefiles", "out_34"))
    )
    filecmp.clear_cache()
    assert filecmp.cmp(item_value, await (await PORTS.outputs)["out_34"].get())


async def test_adding_new_ports(
    special_configuration: Callable,
    postgres_session: sa.orm.session.Session,
):
    config_dict, project_id, node_uuid = special_configuration()
    PORTS = await node_ports_v2.ports()
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
        postgres_session, project_id, node_uuid, config_dict
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
        postgres_session, project_id, node_uuid, config_dict
    )  # pylint: disable=E1101
    await check_config_valid(PORTS, config_dict)


async def test_removing_ports(
    special_configuration: Callable,
    postgres_session: sa.orm.session.Session,
):
    config_dict, project_id, node_uuid = special_configuration(
        inputs=[("in_14", "integer", 15), ("in_17", "boolean", False)],
        outputs=[("out_123", "string", "blahblah"), ("out_2", "number", -12.3)],
    )  # pylint: disable=W0612
    PORTS = await node_ports_v2.ports()
    await check_config_valid(PORTS, config_dict)
    # let's remove the first input
    del config_dict["schema"]["inputs"]["in_14"]
    del config_dict["inputs"]["in_14"]
    np_helpers.update_configuration(
        postgres_session, project_id, node_uuid, config_dict
    )  # pylint: disable=E1101
    await check_config_valid(PORTS, config_dict)
    # let's do the same for the second output
    del config_dict["schema"]["outputs"]["out_2"]
    del config_dict["outputs"]["out_2"]
    np_helpers.update_configuration(
        postgres_session, project_id, node_uuid, config_dict
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
    ],
)
async def test_get_value_from_previous_node(
    special_2nodes_configuration: Callable,
    node_link: Callable,
    item_type: str,
    item_value: ItemConcreteValue,
    item_pytype: Type,
):
    config_dict, _, _ = special_2nodes_configuration(
        prev_node_outputs=[("output_123", item_type, item_value)],
        inputs=[("in_15", item_type, node_link("output_123"))],
    )
    PORTS = await node_ports_v2.ports()

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
    special_2nodes_configuration: Callable,
    project_id: str,
    node_uuid: str,
    filemanager_cfg: None,
    node_link: Callable,
    store_link: Callable,
    item_type: str,
    item_value: str,
    item_pytype: Type,
):
    config_dict, _, _ = special_2nodes_configuration(
        prev_node_outputs=[
            ("output_123", item_type, store_link(item_value, project_id, node_uuid))
        ],
        inputs=[("in_15", item_type, node_link("output_123"))],
        project_id=project_id,
        previous_node_id=node_uuid,
    )
    PORTS = await node_ports_v2.ports()
    await check_config_valid(PORTS, config_dict)
    file_path = await (await PORTS.inputs)["in_15"].get()
    assert isinstance(file_path, item_pytype)
    assert file_path == Path(
        tempfile.gettempdir(), "simcorefiles", "in_15", Path(item_value).name
    )
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
    special_2nodes_configuration: Callable,
    project_id: str,
    node_uuid: str,
    filemanager_cfg: None,
    node_link: Callable,
    store_link: Callable,
    postgres_session: sa.orm.session.Session,
    item_type: str,
    item_value: str,
    item_alias: str,
    item_pytype: Type,
):
    config_dict, _, this_node_uuid = special_2nodes_configuration(
        prev_node_outputs=[
            ("in_15", item_type, store_link(item_value, project_id, node_uuid))
        ],
        inputs=[("in_15", item_type, node_link("in_15"))],
        project_id=project_id,
        previous_node_id=node_uuid,
    )
    PORTS = await node_ports_v2.ports()
    await check_config_valid(PORTS, config_dict)
    # add a filetokeymap
    config_dict["schema"]["inputs"]["in_15"]["fileToKeyMap"] = {item_alias: "in_15"}
    np_helpers.update_configuration(
        postgres_session, project_id, this_node_uuid, config_dict
    )  # pylint: disable=E1101
    await check_config_valid(PORTS, config_dict)
    file_path = await (await PORTS.inputs)["in_15"].get()
    assert isinstance(file_path, item_pytype)
    assert file_path == Path(tempfile.gettempdir(), "simcorefiles", "in_15", item_alias)
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
    special_configuration: Callable,
    project_id: str,
    node_uuid: str,
    filemanager_cfg: None,
    s3_simcore_location: str,
    bucket: str,
    store_link: Callable,
    postgres_session: sa.orm.session.Session,
    item_type: str,
    item_value: str,
    item_alias: str,
    item_pytype: Type,
):
    config_dict, project_id, node_uuid = special_configuration(
        inputs=[("in_1", item_type, store_link(item_value, project_id, node_uuid))],
        outputs=[("out_1", item_type, None)],
        project_id=project_id,
        node_id=node_uuid,
    )
    PORTS = await node_ports_v2.ports()
    await check_config_valid(PORTS, config_dict)
    # add a filetokeymap
    config_dict["schema"]["inputs"]["in_1"]["fileToKeyMap"] = {item_alias: "in_1"}
    config_dict["schema"]["outputs"]["out_1"]["fileToKeyMap"] = {item_alias: "out_1"}
    np_helpers.update_configuration(
        postgres_session, project_id, node_uuid, config_dict
    )  # pylint: disable=E1101
    await check_config_valid(PORTS, config_dict)
    file_path = await (await PORTS.inputs)["in_1"].get()
    assert isinstance(file_path, item_pytype)
    assert file_path == Path(tempfile.gettempdir(), "simcorefiles", "in_1", item_alias)

    # let's get it a second time to see if replacing works
    file_path = await (await PORTS.inputs)["in_1"].get()
    assert isinstance(file_path, item_pytype)
    assert file_path == Path(tempfile.gettempdir(), "simcorefiles", "in_1", item_alias)

    # now set
    invalid_alias = Path("invalid_alias.fjfj")
    with pytest.raises(exceptions.PortNotFound):
        await PORTS.set_file_by_keymap(invalid_alias)

    await PORTS.set_file_by_keymap(file_path)
    file_id = np_helpers.file_uuid(file_path, project_id, node_uuid)
    received_file_link = (await PORTS.outputs)["out_1"].value.dict(
        by_alias=True, exclude_unset=True
    )
    assert received_file_link["store"] == s3_simcore_location
    assert received_file_link["path"] == file_id
    # received a new eTag
    assert received_file_link["eTag"]
