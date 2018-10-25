
#pylint: disable=W0212
#pylint: disable=C0111
import pytest
import helpers
from pathlib import Path
from simcore_sdk.nodeports import config as node_config

def test_access_with_key(default_nodeports_configuration): # pylint: disable=W0613, W0621    
    from simcore_sdk.nodeports.nodeports import PORTS

    assert PORTS.inputs["in_1"].key == PORTS.inputs[0].key
    assert PORTS.inputs["in_5"].value == PORTS.inputs[1].value
    assert PORTS.outputs["out_1"].description == PORTS.outputs[0].description

def create_special_configuration(special_nodeports_configuration, item_key, item_type):
    special_config = helpers.get_empty_config() #pylint: disable=E1101
    special_config["schema"]["outputs"].update({
        item_key:{
        "label": "additional data",
        "description": "here some additional data",
        "displayOrder":2,
        "type": item_type}})
    special_config["outputs"].update({item_key:None})
    special_nodeports_configuration(special_config)

@pytest.mark.parametrize("item_type, item_value", [
    ("integer", 26),
    ("integer", 0),
    ("integer", -52),
    ("number", -746.4748),
    ("number", 0.0),
    ("number", 4566.11235),
    ("boolean", False),    
    ("boolean", True),
    ("string", "test-string"),
    ("string", ""),
])
def test_port_value_accessors_no_s3(special_nodeports_configuration, item_type, item_value): # pylint: disable=W0613, W0621
    item_key = "out_15"
    create_special_configuration(special_nodeports_configuration, item_key, item_type)
    from simcore_sdk.nodeports.nodeports import PORTS
    assert PORTS.outputs[item_key].get() is None
    PORTS.outputs[item_key].set(item_value)
    assert PORTS.outputs[item_key].value == item_value
    converted_value = PORTS.outputs[item_key].get()
    assert isinstance(converted_value, node_config.TYPE_TO_PYTHON_TYPE_MAP[item_type]["type"])
    assert converted_value == item_value

@pytest.mark.parametrize("item_type, item_value", [
    ("data:*/*", __file__)
])
def test_port_value_accessors_s3(special_nodeports_configuration, bucket, item_type, item_value): # pylint: disable=W0613, W0621
    item_key = "out_blah"
    create_special_configuration(special_nodeports_configuration, item_key, item_type)
    import os
    import tempfile
    from simcore_sdk.nodeports.nodeports import PORTS
    assert PORTS.outputs[item_key].get() is None # check emptyness

    # this triggers an upload to S3 + configuration change
    PORTS.outputs[item_key].set(item_value)
    # this is the link to S3 storage
    assert PORTS.outputs[item_key].value == {"store":"s3-z43", "path":Path(os.environ["SIMCORE_PIPELINE_ID"], os.environ["SIMCORE_NODE_UUID"], Path(item_value).name).as_posix()}  
    # this triggers a download from S3 to a location in /tempdir/simcorefiles/item_key
    converted_value = PORTS.outputs[item_key].get()
    assert isinstance(converted_value, Path)

    assert Path(converted_value).exists()
    converted_value_to_check_for = str(Path(tempfile.gettempdir(), "simcorefiles", item_key))
    assert str(PORTS.outputs[item_key].get()).startswith(converted_value_to_check_for)

@pytest.mark.parametrize("item_type, item_value", [
    ("data:*/*", __file__)
])
def test_file_integrity(special_nodeports_configuration, bucket, item_type, item_value): # pylint: disable=W0613, W0621
    item_key = "out_blah"
    create_special_configuration(special_nodeports_configuration, item_key, item_type)
    from simcore_sdk.nodeports.nodeports import PORTS
    assert PORTS.outputs[item_key].get() is None # check emptyness

    # this triggers an upload to S3 + configuration change
    PORTS.outputs[item_key].set(item_value)

    downloaded_file_path = PORTS.outputs[item_key].get()
    import filecmp
    filecmp.clear_cache()
    assert filecmp.cmp(item_value, downloaded_file_path, shallow=False)

# @pytest.mark.skip(reason="SAN: this does not pass on travis but does on my workstation")
def test_adding_new_ports(special_nodeports_configuration):
    special_configuration = helpers.get_empty_config() #pylint: disable=E1101
    engine, session, pipeline_id, node_uuid, _ = special_nodeports_configuration(special_configuration) #pylint: disable=W0612
    from simcore_sdk.nodeports.nodeports import PORTS
    # check empty configuration
    assert not PORTS.inputs
    assert not PORTS.outputs

    # replace the configuration now, add an input
    special_configuration["schema"]["inputs"].update({
        "in_15":{
        "label": "additional data",
        "description": "here some additional data",
        "displayOrder":2,
        "type": "integer"}})
    special_configuration["inputs"].update({"in_15":15})
    helpers.update_configuration(session, pipeline_id, node_uuid, special_configuration) #pylint: disable=E1101

    assert len(PORTS.inputs) == 1
    assert PORTS.inputs[0].key == "in_15"
    assert PORTS.inputs[0].label == "additional data"
    assert PORTS.inputs[0].description == "here some additional data"
    assert PORTS.inputs[0].type == "integer"
    assert PORTS.inputs[0].value == 15

    # # replace the configuration now, add an output
    special_configuration["schema"]["outputs"].update({
        "out_15":{
        "label": "output data",
        "description": "a cool output",
        "displayOrder":2,
        "type": "boolean"}})
    special_configuration["outputs"].update({"in_15":None})
    helpers.update_configuration(session, pipeline_id, node_uuid, special_configuration) #pylint: disable=E1101

    # # no change on inputs
    assert len(PORTS.inputs) == 1
    assert PORTS.inputs[0].key == "in_15"
    assert PORTS.inputs[0].label == "additional data"
    assert PORTS.inputs[0].description == "here some additional data"
    assert PORTS.inputs[0].type == "integer"
    assert PORTS.inputs[0].value == 15
    # # new output
    assert len(PORTS.outputs) == 1
    assert PORTS.outputs[0].key == "out_15"
    assert PORTS.outputs[0].label == "output data"
    assert PORTS.outputs[0].description == "a cool output"
    assert PORTS.outputs[0].type == "boolean"
    assert PORTS.outputs[0].value == None

# @pytest.mark.skip(reason="SAN: this does not pass on travis but does on my workstation")
def test_removing_ports(special_nodeports_configuration):
    special_configuration = helpers.get_empty_config() #pylint: disable=E1101
    # add inputs
    special_configuration["schema"]["inputs"].update({
        "in_15":{
        "label": "additional data",
        "description": "here some additional data",
        "displayOrder":2,
        "type": "integer"}})
    special_configuration["inputs"].update({"in_15":15})
    special_configuration["schema"]["inputs"].update({
        "in_17":{
        "label": "additional data",
        "description": "here some additional data",
        "displayOrder":2,
        "type": "integer"}})
    special_configuration["inputs"].update({"in_17":15})
    special_configuration["schema"]["outputs"].update({
        "out_15":{
        "label": "additional data",
        "description": "here some additional data",
        "displayOrder":2,
        "type": "integer"}})
    special_configuration["outputs"].update({"out_15":15})
    special_configuration["schema"]["outputs"].update({
        "out_17":{
        "label": "additional data",
        "description": "here some additional data",
        "displayOrder":2,
        "type": "integer"}})
    special_configuration["outputs"].update({"out_17":15})

    engine, session, pipeline_id, node_uuid, _ = special_nodeports_configuration(special_configuration) #pylint: disable=W0612
    from simcore_sdk.nodeports.nodeports import PORTS
    assert len(PORTS.inputs) == 2
    assert len(PORTS.outputs) == 2
    # let's remove the first input
    del special_configuration["schema"]["inputs"]["in_15"]
    del special_configuration["inputs"]["in_15"]
    helpers.update_configuration(session, pipeline_id, node_uuid, special_configuration) #pylint: disable=E1101
    assert len(PORTS.inputs) == 1
    assert len(PORTS.outputs) == 2

    assert PORTS.inputs[0].key == "in_17"
    assert PORTS.inputs[0].label == "additional data"
    assert PORTS.inputs[0].description == "here some additional data"
    assert PORTS.inputs[0].type == "integer"
    assert PORTS.inputs[0].value == 15

    # let's do the same for the second output
    del special_configuration["schema"]["outputs"]["out_17"]
    del special_configuration["outputs"]["out_17"]
    helpers.update_configuration(session, pipeline_id, node_uuid, special_configuration) #pylint: disable=E1101
    assert len(PORTS.inputs) == 1
    assert len(PORTS.outputs) == 1

    assert PORTS.outputs[0].key == "out_15"
    assert PORTS.outputs[0].label == "additional data"
    assert PORTS.outputs[0].description == "here some additional data"
    assert PORTS.outputs[0].type == "integer"
    assert PORTS.outputs[0].value == 15

def test_get_file_follows_previous_node(special_nodeports_configuration, s3_client, bucket, tmpdir):
    # create some file on S3
    dummy_file_name = "some_file.ext"
    file_path = Path(tmpdir, dummy_file_name)
    file_path.write_text("test text")    


    previous_node_config = helpers.get_empty_config()  #pylint: disable=E1101    
    previous_node_config["schema"]["outputs"].update({
        "output_123":{
        "label": "additional data",
        "description": "here some additional data",
        "displayOrder":2,
        "type": "data:*/*"}})
    previous_node_config["outputs"].update({"output_123":{"store":"s3-z43", "path":"{file}".format(file=Path("SIMCORE_PIPELINE_ID", "SIMCORE_NODE_UUID",dummy_file_name))}})

    current_node_config = helpers.get_empty_config()  #pylint: disable=E1101
    current_node_config["schema"]["inputs"].update({
        "in_15":{
        "label": "additional data",
        "description": "here some additional data",
        "displayOrder":2,
        "type": "data:*/*"}})
    current_node_config["inputs"].update({"in_15":{"nodeUuid":"SIMCORE_NODE_UUID", "output":"output_123"}})
    # create the initial configuration
    _, session, pipeline_id, node_uuid, other_node_uuids = special_nodeports_configuration(current_node_config, [previous_node_config])    
    assert len(other_node_uuids) == 1
    # update the link to the previous node with the correct uuid
    current_node_config["inputs"]["in_15"]["nodeUuid"] = str(other_node_uuids[0])
    helpers.update_configuration(session, pipeline_id, node_uuid, current_node_config) #pylint: disable=E1101
    # update the previous node with the actual file path
    s3_object_name = Path(str(pipeline_id), str(other_node_uuids[0]), dummy_file_name).as_posix()
    previous_node_config["outputs"]["output_123"]["path"] = s3_object_name
    helpers.update_configuration(session, pipeline_id, other_node_uuids[0], previous_node_config) #pylint: disable=E1101

    from simcore_sdk.nodeports.nodeports import PORTS
    assert len(PORTS.inputs) == 1
    assert PORTS.inputs[0].key == "in_15"
    assert PORTS.inputs["in_15"].label == current_node_config["schema"]["inputs"]["in_15"]["label"]
    assert PORTS.inputs["in_15"].description == current_node_config["schema"]["inputs"]["in_15"]["description"]
    assert PORTS.inputs["in_15"].type == current_node_config["schema"]["inputs"]["in_15"]["type"]
    assert PORTS.inputs["in_15"].value == current_node_config["inputs"]["in_15"]

    # upload some dummy file
    s3_client.upload_file(bucket, str(s3_object_name), str(file_path))

    file_path = PORTS.inputs[0].get()
    assert Path(file_path).exists()
    assert file_path.name == dummy_file_name
    assert Path(file_path).read_text() == "test text"

    file_path2 = PORTS.get("in_15")
    assert Path(file_path2).exists()
    assert file_path2.name == dummy_file_name
    assert Path(file_path2).read_text() == "test text"