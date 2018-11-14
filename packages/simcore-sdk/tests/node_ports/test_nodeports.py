
import filecmp
import tempfile
from pathlib import Path

#pylint: disable=W0212
#pylint: disable=C0111
#pylint: disable=R0913
#pylint: disable=W0104
#pylint: disable=unused-argument
import pytest

from helpers import helpers #pylint: disable=no-name-in-module
from simcore_sdk import node_ports
from simcore_sdk.node_ports import exceptions


def check_port_valid(ports, config_dict: dict, port_type:str, key_name: str, key):
    assert getattr(ports, port_type)[key].key == key_name
    # check required values
    assert getattr(ports, port_type)[key].label == config_dict["schema"][port_type][key_name]["label"]
    assert getattr(ports, port_type)[key].description == config_dict["schema"][port_type][key_name]["description"]
    assert getattr(ports, port_type)[key].type == config_dict["schema"][port_type][key_name]["type"]        
    assert getattr(ports, port_type)[key].displayOrder == config_dict["schema"][port_type][key_name]["displayOrder"]
    # check optional values
    if "defaultValue" in config_dict["schema"][port_type][key_name]:
        assert getattr(ports, port_type)[key].defaultValue == config_dict["schema"][port_type][key_name]["defaultValue"]
    else:
        assert getattr(ports, port_type)[key].defaultValue == None
    if "fileToKeyMap" in config_dict["schema"][port_type][key_name]:
        assert getattr(ports, port_type)[key].fileToKeyMap == config_dict["schema"][port_type][key_name]["fileToKeyMap"]
    else:
        assert getattr(ports, port_type)[key].fileToKeyMap == None
    if "widget" in config_dict["schema"][port_type][key_name]:
        assert getattr(ports, port_type)[key].widget == config_dict["schema"][port_type][key_name]["widget"]
    else:
        assert getattr(ports, port_type)[key].widget == None
    # check payload values
    if key_name in config_dict[port_type]:
        assert getattr(ports, port_type)[key].value == config_dict[port_type][key_name]
    elif "defaultValue" in config_dict["schema"][port_type][key_name]:
        assert getattr(ports, port_type)[key].value == config_dict["schema"][port_type][key_name]["defaultValue"]
    else:
        assert getattr(ports, port_type)[key].value == None

def check_ports_valid(ports, config_dict: dict, port_type:str):
    for key in config_dict["schema"][port_type].keys():        
        # test using "key" name
        check_port_valid(ports, config_dict, port_type, key, key)
        # test using index
        key_index = list(config_dict["schema"][port_type].keys()).index(key)
        check_port_valid(ports, config_dict, port_type, key, key_index)

def check_config_valid(ports, config_dict: dict):
    check_ports_valid(ports, config_dict, "inputs")
    check_ports_valid(ports, config_dict, "outputs")

def test_default_configuration(default_configuration): # pylint: disable=W0613, W0621    
    config_dict = default_configuration    
    check_config_valid(node_ports.ports(), config_dict)

def test_invalid_ports(special_configuration):
    config_dict, _, _ = special_configuration()
    PORTS = node_ports.ports()
    check_config_valid(PORTS, config_dict)

    assert not PORTS.inputs
    assert not PORTS.outputs

    with pytest.raises(exceptions.UnboundPortError, message="Expecting UnboundPortError"):
        PORTS.inputs[0]

    with pytest.raises(exceptions.UnboundPortError, message="Expecting UnboundPortError"):
        PORTS.outputs[0]


@pytest.mark.parametrize("item_type, item_value, item_pytype", [
    ("integer", 26, int),
    ("integer", 0, int),
    ("integer", -52, int),
    ("number", -746.4748, float),
    ("number", 0.0, float),
    ("number", 4566.11235, float),
    ("boolean", False, bool),    
    ("boolean", True, bool),
    ("string", "test-string", str),
    ("string", "", str)
])
@pytest.mark.asyncio
async def test_port_value_accessors(special_configuration, item_type, item_value, item_pytype): # pylint: disable=W0613, W0621
    item_key = "some key"
    config_dict, _, _ = special_configuration(inputs=[(item_key, item_type, item_value)], outputs=[(item_key, item_type, None)])
    PORTS = node_ports.ports()
    check_config_valid(PORTS, config_dict)

    assert isinstance(await PORTS.inputs[item_key].get(), item_pytype)
    assert await PORTS.inputs[item_key].get() == item_value
    assert await PORTS.outputs[item_key].get() is None

    assert isinstance(await PORTS.get(item_key), item_pytype)
    assert await PORTS.get(item_key) == item_value

    await PORTS.outputs[item_key].set(item_value)
    assert PORTS.outputs[item_key].value == item_value
    assert isinstance(await PORTS.outputs[item_key].get(), item_pytype)
    assert await PORTS.outputs[item_key].get() == item_value

@pytest.mark.parametrize("item_type, item_value, item_pytype, config_value", [
    ("data:*/*", __file__, Path, {"store":"simcore.s3", "path":__file__}),
    ("data:text/*", __file__, Path, {"store":"simcore.s3", "path":__file__}),
    ("data:text/py", __file__, Path, {"store":"simcore.s3", "path":__file__}),
])
@pytest.mark.asyncio
async def test_port_file_accessors(special_configuration, storage, filemanager_cfg, s3_simcore_location, bucket, item_type, item_value, item_pytype, config_value): # pylint: disable=W0613, W0621
    config_dict, project_id, node_uuid = special_configuration(inputs=[("in_1", item_type, config_value)], outputs=[("out_34", item_type, None)])
    PORTS = node_ports.ports()
    check_config_valid(PORTS, config_dict)
    assert await PORTS.outputs["out_34"].get() is None # check emptyness
    # with pytest.raises(exceptions.S3InvalidPathError, message="Expecting S3InvalidPathError"):
    #     await PORTS.inputs["in_1"].get()

    # this triggers an upload to S3 + configuration change
    await PORTS.outputs["out_34"].set(item_value)
    # this is the link to S3 storage
    assert PORTS.outputs["out_34"].value == {"store":s3_simcore_location, "path":Path(str(project_id), str(node_uuid), Path(item_value).name).as_posix()}  
    # this triggers a download from S3 to a location in /tempdir/simcorefiles/item_key
    assert isinstance(await PORTS.outputs["out_34"].get(), item_pytype)
    assert (await PORTS.outputs["out_34"].get()).exists()
    assert str(await PORTS.outputs["out_34"].get()).startswith(str(Path(tempfile.gettempdir(), "simcorefiles", "out_34")))
    filecmp.clear_cache()
    assert filecmp.cmp(item_value, await PORTS.outputs["out_34"].get())

def test_adding_new_ports(special_configuration, session):
    config_dict, project_id, node_uuid = special_configuration()
    PORTS = node_ports.ports()
    check_config_valid(PORTS, config_dict)
    # check empty configuration
    assert not PORTS.inputs
    assert not PORTS.outputs

    # replace the configuration now, add an input
    config_dict["schema"]["inputs"].update({
        "in_15":{
        "label": "additional data",
        "description": "here some additional data",
        "displayOrder":2,
        "type": "integer"}})
    config_dict["inputs"].update({"in_15":15})
    helpers.update_configuration(session, project_id, node_uuid, config_dict) #pylint: disable=E1101
    check_config_valid(PORTS, config_dict)

    # # replace the configuration now, add an output
    config_dict["schema"]["outputs"].update({
        "out_15":{
        "label": "output data",
        "description": "a cool output",
        "displayOrder":2,
        "type": "boolean"}})    
    helpers.update_configuration(session, project_id, node_uuid, config_dict) #pylint: disable=E1101
    check_config_valid(PORTS, config_dict)

def test_removing_ports(special_configuration, session):
    config_dict, project_id, node_uuid = special_configuration(inputs=[("in_14", "integer", 15), 
                                                                        ("in_17", "boolean", False)],
                                                                outputs=[("out_123", "string", "blahblah"),
                                                                        ("out_2", "number", -12.3)]) #pylint: disable=W0612
    PORTS = node_ports.ports()
    check_config_valid(PORTS, config_dict)
    # let's remove the first input
    del config_dict["schema"]["inputs"]["in_14"]
    del config_dict["inputs"]["in_14"]
    helpers.update_configuration(session, project_id, node_uuid, config_dict) #pylint: disable=E1101
    check_config_valid(PORTS, config_dict)
    # let's do the same for the second output
    del config_dict["schema"]["outputs"]["out_2"]
    del config_dict["outputs"]["out_2"]
    helpers.update_configuration(session, project_id, node_uuid, config_dict) #pylint: disable=E1101
    check_config_valid(PORTS, config_dict)

@pytest.mark.parametrize("item_type, item_value, item_pytype", [
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
])
@pytest.mark.asyncio
async def test_get_value_from_previous_node(special_2nodes_configuration, node_link, item_type, item_value, item_pytype):
    config_dict, _, _ = special_2nodes_configuration(prev_node_outputs=[("output_123", item_type, item_value)],
                                                    inputs=[("in_15", item_type, node_link("output_123"))])
    PORTS = node_ports.ports()
    
    check_config_valid(PORTS, config_dict)
    input_value = await PORTS.inputs["in_15"].get()
    assert isinstance(input_value, item_pytype)
    assert await PORTS.inputs["in_15"].get() == item_value

@pytest.mark.parametrize("item_type, item_value, item_pytype", [
    ("data:*/*", __file__, Path),
    ("data:text/*", __file__, Path),
    ("data:text/py", __file__, Path),
])
@pytest.mark.asyncio
async def test_get_file_from_previous_node(special_2nodes_configuration, project_id, node_uuid, filemanager_cfg, node_link, store_link, item_type, item_value, item_pytype):
    config_dict, _, _ = special_2nodes_configuration(prev_node_outputs=[("output_123", item_type, store_link(item_value, project_id, node_uuid))],
                                                    inputs=[("in_15", item_type, node_link("output_123"))], 
                                                    project_id=project_id, previous_node_id=node_uuid)
    PORTS = node_ports.ports()
    check_config_valid(PORTS, config_dict)
    file_path = await PORTS.inputs["in_15"].get()
    assert isinstance(file_path, item_pytype)
    assert file_path == Path(tempfile.gettempdir(), "simcorefiles", "in_15", Path(item_value).name)
    assert file_path.exists()
    filecmp.clear_cache()
    assert filecmp.cmp(file_path, item_value)

@pytest.mark.parametrize("item_type, item_value, item_alias, item_pytype", [
    ("data:*/*", __file__, "some funky name.txt", Path),
    ("data:text/*", __file__, "some funky name without extension", Path),
    ("data:text/py", __file__, "öä$äö2-34 name without extension", Path),
])
@pytest.mark.asyncio
async def test_file_mapping(special_configuration, project_id, node_uuid, filemanager_cfg, s3_simcore_location, bucket, store_link, session, item_type, item_value, item_alias, item_pytype):
    config_dict, project_id, node_uuid = special_configuration(inputs=[("in_1", item_type, store_link(item_value, project_id, node_uuid))], outputs=[("out_1", item_type, None)], project_id=project_id, node_id=node_uuid)
    PORTS = node_ports.ports()
    check_config_valid(PORTS, config_dict)
    # add a filetokeymap
    config_dict["schema"]["inputs"]["in_1"]["fileToKeyMap"] = {item_alias:"in_1"}
    config_dict["schema"]["outputs"]["out_1"]["fileToKeyMap"] = {item_alias:"out_1"}
    helpers.update_configuration(session, project_id, node_uuid, config_dict) #pylint: disable=E1101
    check_config_valid(PORTS, config_dict)
    file_path = await PORTS.inputs["in_1"].get()
    assert isinstance(file_path, item_pytype)
    assert file_path == Path(tempfile.gettempdir(), "simcorefiles", "in_1", item_alias)

    invalid_alias = Path("invalid_alias.fjfj")
    with pytest.raises(exceptions.PortNotFound, message="Expecting PortNotFound"):
        await PORTS.set_file_by_keymap(invalid_alias)
    
    await PORTS.set_file_by_keymap(file_path)
    file_id = helpers.file_uuid(file_path, project_id, node_uuid)
    assert PORTS.outputs["out_1"].value == {"store":s3_simcore_location, "path": file_id}
