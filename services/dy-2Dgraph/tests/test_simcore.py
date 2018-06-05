
#pylint: disable=W0212
#pylint: disable=C0111
import pytest

@pytest.fixture()
def default_simcore_configuration():
    import os
    default_config_path = os.path.join(os.path.dirname(
        os.path.realpath(__file__)), r"../config/connection_config.json")
    os.environ["SIMCORE_CONFIG_PATH"] = default_config_path    

@pytest.fixture()
def special_simcore_configuration(request):
    def create_special_config(configuration):
        import os
        import json
        import tempfile
        # create temporary json file
        temp_file = tempfile.NamedTemporaryFile()
        temp_file.close()
        # ensure the file is removed at the end whatever happens

        def fin():
            if os.path.exists(temp_file.name):
                os.unlink(temp_file.name)
            assert not os.path.exists(temp_file.name)
        request.addfinalizer(fin)
        # get the configuration to set up
        config = configuration
        assert config
        # create the special configuration file
        with open(temp_file.name, "w") as file_pointer:
            json.dump(config, file_pointer)
        assert os.path.exists(temp_file.name)
        # set the environment variable such that simcore will use the special file
        os.environ["SIMCORE_CONFIG_PATH"] = temp_file.name
        return temp_file.name
    return create_special_config

def get_empty_config():
    return {
        "version": "0.1",
        "inputs": [
        ],
        "outputs": [
        ]
    }

def test_default_configuration(default_simcore_configuration): # pylint: disable=W0613, W0621
    from simcore_api import PORTS

    assert len(PORTS.inputs) == 2
    assert PORTS.inputs[0].key == "in_1"
    assert PORTS.inputs[0].label == "computational data"
    assert PORTS.inputs[0].description == "these are computed data out of a pipeline"
    assert PORTS.inputs[0].type == "file-url"
    assert PORTS.inputs[0].value == "/home/jovyan/data/outputControllerOut.dat"
    assert PORTS.inputs[0].timestamp == "2018-05-23T15:34:53.511Z"

    assert PORTS.inputs[1].key == "in_5"
    assert PORTS.inputs[1].label == "some number"
    assert PORTS.inputs[1].description == "numbering things"
    assert PORTS.inputs[1].type == "int"
    assert PORTS.inputs[1].value == "666"
    assert PORTS.inputs[1].timestamp == "2018-05-23T15:34:53.511Z"

    assert len(PORTS.outputs) == 1
    assert PORTS.outputs[0].key == "out_1"
    assert PORTS.outputs[0].label == "some boolean output"
    assert PORTS.outputs[0].description == "could be true or false..."
    assert PORTS.outputs[0].type == "bool"
    assert PORTS.outputs[0].value == "null"
    assert PORTS.outputs[0].timestamp == "2018-05-23T15:34:53.511Z"

def test_access_with_key(default_simcore_configuration): # pylint: disable=W0613, W0621
    from simcore_api import PORTS

    assert PORTS.inputs["in_1"] == PORTS.inputs[0]
    assert PORTS.inputs["in_5"] == PORTS.inputs[1]
    assert PORTS.outputs["out_1"] == PORTS.outputs[0]

def test_port_value_getters(default_simcore_configuration): # pylint: disable=W0613, W0621
    from simcore_api import PORTS

    assert PORTS.inputs["in_1"].get() == "/home/jovyan/data/outputControllerOut.dat"
    assert PORTS.inputs["in_5"].get() == 666
    assert PORTS.outputs["out_1"].get() is None

def test_port_value_setters(special_simcore_configuration): # pylint: disable=W0613, W0621
    
    special_config = get_empty_config()
    special_config["outputs"].append({
        "key": "out_15",
        "label": "additional data",
        "description": "here some additional data",
        "type": "int",
        "value": "null",
        "timestamp": "2018-05-22T19:34:53.511Z"
    })
    special_simcore_configuration(special_config)
    from simcore_api import PORTS
    from simcore_api.simcore import DataItem
    from simcore_api import exceptions

    assert PORTS.outputs["out_15"].get() is None

    modified_output = DataItem(key="out_15", 
                               label="new additional data", 
                               description="new description", 
                               type="bool", 
                               value="True", 
                               timestamp="2018-05-28T19:34:53.511Z")

    with pytest.raises(exceptions.ReadOnlyError, message="Expecting ReadOnlyError") as excinfo:
        PORTS.outputs["out_15"] = modified_output
    assert "Trying to modify read-only object" in str(excinfo.value)                           
    
    PORTS.outputs["out_15"].set(26)
    assert PORTS.outputs["out_15"].get() == 26

def test_default_json_encoding(default_simcore_configuration): # pylint: disable=W0613, W0621
    from simcore_api import PORTS
    from simcore_api.simcore import _SimcoreEncoder
    import json
    import os

    json_data = json.dumps(PORTS, cls=_SimcoreEncoder)
    default_config_path = os.path.join(os.path.dirname(
        os.path.realpath(__file__)), r"../config/connection_config.json")
    with open(default_config_path) as file:
        original_json_data = file.read()
    assert json.loads(json_data) == json.loads(original_json_data)


#pylint: disable=w0621

def test_wrong_version(special_simcore_configuration):
    special_configuration = get_empty_config()
    #change version to a different one
    special_configuration["version"] = "0.0"
    special_simcore_configuration(special_configuration)

    from simcore_api import exceptions    
    with pytest.raises(exceptions.WrongProtocolVersionError, message="Expecting WrongProtocolVersionError") as excinfo:
        from simcore_api import PORTS
        print(PORTS.inputs)
    assert "Expecting version 0.1, found version 0.0" in str(excinfo.value)

def test_invalid_configuration(special_simcore_configuration):
    special_configuration = {"whatever":"stuff"}
    special_simcore_configuration(special_configuration)

    from simcore_api import exceptions
    with pytest.raises(exceptions.InvalidProtocolError, message="Expecting WrongProtocol") as excinfo:
        from simcore_api import PORTS
        print(PORTS.inputs)
    assert "Invalid protocol used in" in str(excinfo.value)

def test_noinputsoutputs(special_simcore_configuration):
    # create empty configuration
    special_configuration = get_empty_config()
    special_simcore_configuration(special_configuration)

    from simcore_api import PORTS
    from simcore_api import exceptions

    assert not PORTS.inputs
    assert not PORTS.outputs

    with pytest.raises(exceptions.UnboundPortError, message="Expecting UnboundPortError") as excinfo:
        input0 = PORTS.inputs[0]
        print(input0)
    assert "No port bound at index" in str(excinfo.value)

    with pytest.raises(exceptions.UnboundPortError, message="Expecting UnboundPortError") as excinfo:
        output0 = PORTS.outputs[0]
        print(output0)
    assert "No port bound at index" in str(excinfo.value)


def update_config_file(path, config):
    import json
    with open(path, "w") as json_file:
        json.dump(config, json_file)


def test_adding_new_ports(special_simcore_configuration):
    special_configuration = get_empty_config()
    config_file = special_simcore_configuration(special_configuration)
    from simcore_api import PORTS
    # check empty configuration
    assert not PORTS.inputs
    assert not PORTS.outputs

    # replace the configuration now, add an input
    special_configuration["inputs"].append({
        "key": "in_15",
        "label": "additional data",
        "description": "here some additional data",
        "type": "int",
        "value": "15",
        "timestamp": "2018-05-22T19:34:53.511Z"
    })
    update_config_file(config_file, special_configuration)

    assert len(PORTS.inputs) == 1
    assert PORTS.inputs[0].key == "in_15"
    assert PORTS.inputs[0].label == "additional data"
    assert PORTS.inputs[0].description == "here some additional data"
    assert PORTS.inputs[0].type == "int"
    assert PORTS.inputs[0].value == "15"
    assert PORTS.inputs[0].timestamp == "2018-05-22T19:34:53.511Z"

    # replace the configuration now, add an output
    special_configuration["outputs"].append({
        "key": "out_15",
        "label": "output data",
        "description": "a cool output",
        "type": "bool",
        "value": "null",
        "timestamp": "2018-05-22T19:34:53.511Z"
    })
    update_config_file(config_file, special_configuration)

    # no change on inputs
    assert len(PORTS.inputs) == 1
    assert PORTS.inputs[0].key == "in_15"
    assert PORTS.inputs[0].label == "additional data"
    assert PORTS.inputs[0].description == "here some additional data"
    assert PORTS.inputs[0].type == "int"
    assert PORTS.inputs[0].value == "15"
    assert PORTS.inputs[0].timestamp == "2018-05-22T19:34:53.511Z"
    # new output
    assert len(PORTS.outputs) == 1
    assert PORTS.outputs[0].key == "out_15"
    assert PORTS.outputs[0].label == "output data"
    assert PORTS.outputs[0].description == "a cool output"
    assert PORTS.outputs[0].type == "bool"
    assert PORTS.outputs[0].value == "null"
    assert PORTS.outputs[0].timestamp == "2018-05-22T19:34:53.511Z"


def test_removing_ports(special_simcore_configuration):
    special_configuration = get_empty_config()
    # add inputs
    special_configuration["inputs"].append({
        "key": "in_15",
        "label": "additional data",
        "description": "here some additional data",
        "type": "int",
        "value": "15",
        "timestamp": "2018-05-22T19:34:53.511Z"
    })
    special_configuration["inputs"].append({
        "key": "in_17",
        "label": "additional data",
        "description": "here some additional data",
        "type": "int",
        "value": "15",
        "timestamp": "2018-05-22T19:34:53.511Z"
    })
    special_configuration["outputs"].append({
        "key": "out_15",
        "label": "additional data",
        "description": "here some additional data",
        "type": "int",
        "value": "15",
        "timestamp": "2018-05-22T19:34:53.511Z"
    })
    special_configuration["outputs"].append({
        "key": "out_17",
        "label": "additional data",
        "description": "here some additional data",
        "type": "int",
        "value": "15",
        "timestamp": "2018-05-22T19:34:53.511Z"
    })

    config_file = special_simcore_configuration(special_configuration)
    from simcore_api import PORTS
    assert len(PORTS.inputs) == 2
    assert len(PORTS.outputs) == 2
    # let's remove the first input
    del special_configuration["inputs"][0]
    update_config_file(config_file, special_configuration)
    assert len(PORTS.inputs) == 1
    assert len(PORTS.outputs) == 2

    assert PORTS.inputs[0].key == "in_17"
    assert PORTS.inputs[0].label == "additional data"
    assert PORTS.inputs[0].description == "here some additional data"
    assert PORTS.inputs[0].type == "int"
    assert PORTS.inputs[0].value == "15"
    assert PORTS.inputs[0].timestamp == "2018-05-22T19:34:53.511Z"

    # let's do the same for the second output
    del special_configuration["outputs"][1]
    update_config_file(config_file, special_configuration)
    assert len(PORTS.inputs) == 1
    assert len(PORTS.outputs) == 1

    assert PORTS.outputs[0].key == "out_15"
    assert PORTS.outputs[0].label == "additional data"
    assert PORTS.outputs[0].description == "here some additional data"
    assert PORTS.outputs[0].type == "int"
    assert PORTS.outputs[0].value == "15"
    assert PORTS.outputs[0].timestamp == "2018-05-22T19:34:53.511Z"

def test_changing_inputs_error(default_simcore_configuration): # pylint: disable=W0613
    from simcore_api import PORTS
    from simcore_api.simcore import DataItemsList
    from simcore_api import exceptions

    with pytest.raises(exceptions.ReadOnlyError, message="Expecting ReadOnlyError") as excinfo:
        PORTS.inputs = DataItemsList()
    assert "Trying to modify read-only object" in str(excinfo.value)


    from simcore_api.simcore import DataItem
    new_input = DataItem(key="dummy_1", 
                         label="new label", 
                         description="new description", 
                         type="int", 
                         value="233", 
                         timestamp="2018-06-04T09:46:43:343")
    with pytest.raises(exceptions.ReadOnlyError, message="Expecting ReadOnlyError") as excinfo:
        PORTS.inputs[1] = new_input
    assert "Trying to modify read-only object" in str(excinfo.value)

def test_changing_outputs_error(default_simcore_configuration): # pylint: disable=W0613
    from simcore_api import PORTS
    from simcore_api.simcore import DataItemsList
    from simcore_api import exceptions

    with pytest.raises(exceptions.ReadOnlyError, message="Expecting ReadOnlyError") as excinfo:
        PORTS.outputs = DataItemsList()
    assert "Trying to modify read-only object" in str(excinfo.value)


    from simcore_api.simcore import DataItem
    new_output = DataItem(key="dummy_1", 
                          label="new label", 
                          description="new description", 
                          type="int", 
                          value="233", 
                          timestamp="2018-06-04T09:46:43:343")
     
    with pytest.raises(exceptions.ReadOnlyError, message="Expecting ReadOnlyError") as excinfo:
        PORTS.outputs[0] = new_output
    assert "Trying to modify read-only object" in str(excinfo.value)
