
#pylint: disable=W0212
#pylint: disable=C0111
import pytest
from pathlib import Path
from simcore_sdk.nodeports import config as node_config

def test_access_with_key(default_nodeports_configuration): # pylint: disable=W0613, W0621
    from simcore_sdk.nodeports.nodeports import PORTS

    assert PORTS.inputs["in_1"] == PORTS.inputs[0]
    assert PORTS.inputs["in_5"] == PORTS.inputs[1]
    assert PORTS.outputs["out_1"] == PORTS.outputs[0]

@pytest.mark.parametrize("item_type, item_value", [
    ("integer", 26),
    ("integer", 0),
    ("integer", -52),
    ("number", -746.4748),
    ("number", 0.0),
    ("number", 4566.11235),
    ("bool", False),    
    ("bool", True),
    ("string", "test-string"),
    ("string", ""),
])
def test_port_value_accessors_no_s3(special_nodeports_configuration, item_type, item_value): # pylint: disable=W0613, W0621
    import helpers
    special_config = helpers.get_empty_config() #pylint: disable=E1101
    special_config["outputs"].append({
        "key": "out_15",
        "label": "additional data",
        "desc": "here some additional data",
        "type": item_type,
        "value": "null",
        "timestamp": "2018-05-22T19:34:53.511Z"
    })
    special_nodeports_configuration(special_config)
    from simcore_sdk.nodeports.nodeports import PORTS
    assert PORTS.outputs["out_15"].get() is None

    PORTS.outputs["out_15"].set(item_value)
    assert PORTS.outputs["out_15"].value == str(item_value)
    converted_value = PORTS.outputs["out_15"].get()
    assert isinstance(converted_value, node_config.TYPE_TO_PYTHON_TYPE_MAP[item_type]["type"])
    assert converted_value == item_value

@pytest.mark.parametrize("item_type, item_value", [
    ("file-url", __file__),
    ("folder-url", str(Path(__file__).parent))
])
def test_port_value_accessors_s3(special_nodeports_configuration, bucket, item_type, item_value): # pylint: disable=W0613, W0621
    import helpers
    import os
    import tempfile
    special_config = helpers.get_empty_config() #pylint: disable=E1101
    item_key = "out_blah"
    special_config["outputs"].append({
        "key": item_key,
        "label": "additional data",
        "desc": "here some additional data",
        "type": item_type,
        "value": "null",
        "timestamp": "2018-05-22T19:34:53.511Z"
    })
    special_nodeports_configuration(special_config)
    from simcore_sdk.nodeports.nodeports import PORTS
    assert PORTS.outputs[item_key].get() is None # check emptyness

    # this triggers an upload to S3 + configuration change
    PORTS.outputs[item_key].set(item_value)
    # this is the link to S3 storage
    assert PORTS.outputs[item_key].value == ".".join(["link", os.environ["SIMCORE_NODE_UUID"], item_key])
    # this triggers a download from S3 to a location in /tempdir/simcorefiles/item_key or /tempdir/simcorefiles/item_key/item_key.simcore
    converted_value = PORTS.outputs[item_key].get()
    assert isinstance(converted_value, node_config.TYPE_TO_PYTHON_TYPE_MAP[item_type]["type"])

    assert Path(converted_value).exists()
    converted_value_to_check_for = str(Path(tempfile.gettempdir(), "simcorefiles", item_key))
    assert PORTS.outputs[item_key].get().startswith(converted_value_to_check_for)

def test_file_integrity(special_nodeports_configuration, bucket): # pylint: disable=W0613, W0621
    import helpers
    special_config = helpers.get_empty_config() #pylint: disable=E1101
    item_key = "out_blah"
    special_config["outputs"].append({
        "key": item_key,
        "label": "additional data",
        "desc": "here some additional data",
        "type": "file-url",
        "value": "null",
        "timestamp": "2018-05-22T19:34:53.511Z"
    })
    special_nodeports_configuration(special_config)
    from simcore_sdk.nodeports.nodeports import PORTS
    assert PORTS.outputs[item_key].get() is None # check emptyness

    # this triggers an upload to S3 + configuration change
    PORTS.outputs[item_key].set(__file__)

    downloaded_file_path = PORTS.outputs[item_key].get()
    import filecmp
    filecmp.clear_cache()
    assert filecmp.cmp(__file__, downloaded_file_path, shallow=False)

def test_folder_integrity(special_nodeports_configuration, bucket): # pylint: disable=W0613, W0621
    import helpers
    special_config = helpers.get_empty_config() #pylint: disable=E1101
    item_key = "out_blah"
    special_config["outputs"].append({
        "key": item_key,
        "label": "additional data",
        "desc": "here some additional data",
        "type": "folder-url",
        "value": "null",
        "timestamp": "2018-05-22T19:34:53.511Z"
    })
    special_nodeports_configuration(special_config)
    from simcore_sdk.nodeports.nodeports import PORTS
    assert PORTS.outputs[item_key].get() is None # check emptyness

    # this triggers an upload to S3 + configuration change
    original_path = str(Path(__file__).parent)
    PORTS.outputs[item_key].set(original_path)
    downloaded_folder_path = PORTS.outputs[item_key].get()

    original_files = [f for f in Path(original_path).glob("*") if f.is_file()]
    downloaded_files = list(Path(downloaded_folder_path).glob("*"))

    assert len(original_files) == len(downloaded_files)

    import filecmp
    for i in range(len(original_files)):
        assert filecmp.cmp(original_files[i], downloaded_files[i])
    

@pytest.mark.skip(reason="SAN: this does not pass on travis but does on my workstation")
def test_adding_new_ports(special_nodeports_configuration):
    import helpers
    special_configuration = helpers.get_empty_config() #pylint: disable=E1101
    engine, session, pipeline_id, node_uuid = special_nodeports_configuration(special_configuration) #pylint: disable=W0612
    from simcore_sdk.nodeports.nodeports import PORTS
    # check empty configuration
    assert not PORTS.inputs
    assert not PORTS.outputs

    # replace the configuration now, add an input
    special_configuration["inputs"].append({
        "key": "in_15",
        "label": "additional data",
        "desc": "here some additional data",
        "type": "integer",
        "value": "15",
        "timestamp": "2018-05-22T19:34:53.511Z"
    })
    helpers.update_configuration(session, pipeline_id, node_uuid, special_configuration) #pylint: disable=E1101

    assert len(PORTS.inputs) == 1
    assert PORTS.inputs[0].key == "in_15"
    assert PORTS.inputs[0].label == "additional data"
    assert PORTS.inputs[0].desc == "here some additional data"
    assert PORTS.inputs[0].type == "integer"
    assert PORTS.inputs[0].value == "15"
    assert PORTS.inputs[0].timestamp == "2018-05-22T19:34:53.511Z"

    # # replace the configuration now, add an output
    special_configuration["outputs"].append({
        "key": "out_15",
        "label": "output data",
        "desc": "a cool output",
        "type": "bool",
        "value": "null",
        "timestamp": "2018-05-22T19:34:53.511Z"
    })
    helpers.update_configuration(session, pipeline_id, node_uuid, special_configuration) #pylint: disable=E1101

    # # no change on inputs
    assert len(PORTS.inputs) == 1
    assert PORTS.inputs[0].key == "in_15"
    assert PORTS.inputs[0].label == "additional data"
    assert PORTS.inputs[0].desc == "here some additional data"
    assert PORTS.inputs[0].type == "integer"
    assert PORTS.inputs[0].value == "15"
    assert PORTS.inputs[0].timestamp == "2018-05-22T19:34:53.511Z"
    # # new output
    assert len(PORTS.outputs) == 1
    assert PORTS.outputs[0].key == "out_15"
    assert PORTS.outputs[0].label == "output data"
    assert PORTS.outputs[0].desc == "a cool output"
    assert PORTS.outputs[0].type == "bool"
    assert PORTS.outputs[0].value == "null"
    assert PORTS.outputs[0].timestamp == "2018-05-22T19:34:53.511Z"

@pytest.mark.skip(reason="SAN: this does not pass on travis but does on my workstation")
def test_removing_ports(special_nodeports_configuration):
    import helpers    
    special_configuration = helpers.get_empty_config() #pylint: disable=E1101
    # add inputs
    special_configuration["inputs"].append({
        "key": "in_15",
        "label": "additional data",
        "desc": "here some additional data",
        "type": "integer",
        "value": "15",
        "timestamp": "2018-05-22T19:34:53.511Z"
    })
    special_configuration["inputs"].append({
        "key": "in_17",
        "label": "additional data",
        "desc": "here some additional data",
        "type": "integer",
        "value": "15",
        "timestamp": "2018-05-22T19:34:53.511Z"
    })
    special_configuration["outputs"].append({
        "key": "out_15",
        "label": "additional data",
        "desc": "here some additional data",
        "type": "integer",
        "value": "15",
        "timestamp": "2018-05-22T19:34:53.511Z"
    })
    special_configuration["outputs"].append({
        "key": "out_17",
        "label": "additional data",
        "desc": "here some additional data",
        "type": "integer",
        "value": "15",
        "timestamp": "2018-05-22T19:34:53.511Z"
    })

    engine, session, pipeline_id, node_uuid = special_nodeports_configuration(special_configuration) #pylint: disable=W0612
    from simcore_sdk.nodeports.nodeports import PORTS
    assert len(PORTS.inputs) == 2
    assert len(PORTS.outputs) == 2
    # let's remove the first input
    del special_configuration["inputs"][0]
    helpers.update_configuration(session, pipeline_id, node_uuid, special_configuration) #pylint: disable=E1101
    assert len(PORTS.inputs) == 1
    assert len(PORTS.outputs) == 2

    assert PORTS.inputs[0].key == "in_17"
    assert PORTS.inputs[0].label == "additional data"
    assert PORTS.inputs[0].desc == "here some additional data"
    assert PORTS.inputs[0].type == "integer"
    assert PORTS.inputs[0].value == "15"
    assert PORTS.inputs[0].timestamp == "2018-05-22T19:34:53.511Z"

    # let's do the same for the second output
    del special_configuration["outputs"][1]
    helpers.update_configuration(session, pipeline_id, node_uuid, special_configuration) #pylint: disable=E1101
    assert len(PORTS.inputs) == 1
    assert len(PORTS.outputs) == 1

    assert PORTS.outputs[0].key == "out_15"
    assert PORTS.outputs[0].label == "additional data"
    assert PORTS.outputs[0].desc == "here some additional data"
    assert PORTS.outputs[0].type == "integer"
    assert PORTS.outputs[0].value == "15"
    assert PORTS.outputs[0].timestamp == "2018-05-22T19:34:53.511Z"

def test_changing_inputs_error(default_nodeports_configuration): # pylint: disable=W0613
    from simcore_sdk.nodeports.nodeports import PORTS
    from simcore_sdk.nodeports.nodeports import DataItemsList
    from simcore_sdk.nodeports import exceptions

    with pytest.raises(exceptions.ReadOnlyError, message="Expecting ReadOnlyError") as excinfo:
        PORTS.inputs = DataItemsList()
    assert "Trying to modify read-only object" in str(excinfo.value)


    from simcore_sdk.nodeports._item import DataItem
    new_input = DataItem(key="dummy_1", 
                         label="new label", 
                         desc="new description", 
                         type="integer", 
                         value="233", 
                         timestamp="2018-06-04T09:46:43:343")
    with pytest.raises(exceptions.ReadOnlyError, message="Expecting ReadOnlyError") as excinfo:
        PORTS.inputs[1] = new_input
    assert "Trying to modify read-only object" in str(excinfo.value)

def test_changing_outputs_error(default_nodeports_configuration): # pylint: disable=W0613
    from simcore_sdk.nodeports.nodeports import PORTS
    from simcore_sdk.nodeports.nodeports import DataItemsList
    from simcore_sdk.nodeports import exceptions

    with pytest.raises(exceptions.ReadOnlyError, message="Expecting ReadOnlyError") as excinfo:
        PORTS.outputs = DataItemsList()
    assert "Trying to modify read-only object" in str(excinfo.value)


    from simcore_sdk.nodeports._item import DataItem
    new_output = DataItem(key="dummy_1", 
                          label="new label", 
                          desc="new description", 
                          type="integer", 
                          value="233", 
                          timestamp="2018-06-04T09:46:43:343")
     
    with pytest.raises(exceptions.ReadOnlyError, message="Expecting ReadOnlyError") as excinfo:
        PORTS.outputs[0] = new_output
    assert "Trying to modify read-only object" in str(excinfo.value)
