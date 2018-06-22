
#pylint: disable=W0212
#pylint: disable=C0111
import pytest

def test_access_with_key(default_nodeports_configuration): # pylint: disable=W0613, W0621
    from simcore_sdk.nodeports.nodeports import PORTS

    assert PORTS.inputs["in_1"] == PORTS.inputs[0]
    assert PORTS.inputs["in_5"] == PORTS.inputs[1]
    assert PORTS.outputs["out_1"] == PORTS.outputs[0]

def test_port_value_getters(default_nodeports_configuration): # pylint: disable=W0613, W0621
    from simcore_sdk.nodeports.nodeports import PORTS

    assert PORTS.inputs["in_1"].get() == "/home/jovyan/data/outputControllerOut.dat"
    assert PORTS.inputs["in_5"].get() == 666
    assert PORTS.outputs["out_1"].get() is None

def test_port_value_setters(special_nodeports_configuration): # pylint: disable=W0613, W0621
    import helpers
    special_config = helpers.get_empty_config() #pylint: disable=E1101
    special_config["outputs"].append({
        "key": "out_15",
        "label": "additional data",
        "desc": "here some additional data",
        "type": "int",
        "value": "null",
        "timestamp": "2018-05-22T19:34:53.511Z"
    })
    special_nodeports_configuration(special_config)
    from simcore_sdk.nodeports.nodeports import PORTS

    assert PORTS.outputs["out_15"].get() is None

    PORTS.outputs["out_15"].set(26)
    assert PORTS.outputs["out_15"].get() == 26

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
        "type": "int",
        "value": "15",
        "timestamp": "2018-05-22T19:34:53.511Z"
    })
    helpers.update_configuration(session, pipeline_id, node_uuid, special_configuration) #pylint: disable=E1101

    assert len(PORTS.inputs) == 1
    assert PORTS.inputs[0].key == "in_15"
    assert PORTS.inputs[0].label == "additional data"
    assert PORTS.inputs[0].desc == "here some additional data"
    assert PORTS.inputs[0].type == "int"
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
    assert PORTS.inputs[0].type == "int"
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
        "type": "int",
        "value": "15",
        "timestamp": "2018-05-22T19:34:53.511Z"
    })
    special_configuration["inputs"].append({
        "key": "in_17",
        "label": "additional data",
        "desc": "here some additional data",
        "type": "int",
        "value": "15",
        "timestamp": "2018-05-22T19:34:53.511Z"
    })
    special_configuration["outputs"].append({
        "key": "out_15",
        "label": "additional data",
        "desc": "here some additional data",
        "type": "int",
        "value": "15",
        "timestamp": "2018-05-22T19:34:53.511Z"
    })
    special_configuration["outputs"].append({
        "key": "out_17",
        "label": "additional data",
        "desc": "here some additional data",
        "type": "int",
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
    assert PORTS.inputs[0].type == "int"
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
    assert PORTS.outputs[0].type == "int"
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
                         type="int", 
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
                          type="int", 
                          value="233", 
                          timestamp="2018-06-04T09:46:43:343")
     
    with pytest.raises(exceptions.ReadOnlyError, message="Expecting ReadOnlyError") as excinfo:
        PORTS.outputs[0] = new_output
    assert "Trying to modify read-only object" in str(excinfo.value)
