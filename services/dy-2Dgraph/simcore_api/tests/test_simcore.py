
#pylint: disable=W0212
#pylint: disable=C0111
import pytest


def test_default_configuration():
    from .. import simcore

    assert len(simcore.inputs) == 2
    assert simcore.inputs[0].key == "in_1"
    assert simcore.inputs[0].label == "computational data"
    assert simcore.inputs[0].description == "these are computed data out of a pipeline"
    assert simcore.inputs[0].type == "file-url"
    assert simcore.inputs[0].value == "/home/jovyan/data/outputControllerOut.dat"
    assert simcore.inputs[0].timestamp == "2018-05-23T15:34:53.511Z"

    assert simcore.inputs[1].key == "in_5"
    assert simcore.inputs[1].label == "some number"
    assert simcore.inputs[1].description == "numbering things"
    assert simcore.inputs[1].type == "integer"
    assert simcore.inputs[1].value == "666"
    assert simcore.inputs[1].timestamp == "2018-05-23T15:34:53.511Z"

    assert len(simcore.outputs) == 1
    assert simcore.outputs[0].key == "out_1"
    assert simcore.outputs[0].label == "some boolean output"
    assert simcore.outputs[0].description == "could be true or false..."
    assert simcore.outputs[0].type == "bool"
    assert simcore.outputs[0].value == "null"
    assert simcore.outputs[0].timestamp == "2018-05-23T15:34:53.511Z"

def test_default_json_encoding():
    from .. import simcore
    from ..simcore import _SimcoreEncoder
    import json
    import os

    json_data = json.dumps(simcore, cls=_SimcoreEncoder)
    default_config_path = os.path.join(os.path.dirname(
        os.path.realpath(__file__)), r"../../config/connection_config.json")
    with open(default_config_path) as file:
        original_json_data = file.read()
    assert json.loads(json_data) == json.loads(original_json_data)


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
#pylint: disable=w0621

def test_wrong_version(special_simcore_configuration):
    special_configuration = get_empty_config()
    #change version to a different one
    special_configuration["version"] = "0.0"
    special_simcore_configuration(special_configuration)

    from .. import exceptions    
    with pytest.raises(exceptions.WrongProtocolVersionError, message="Expecting WrongProtocolVersionError") as excinfo:
        from .. import simcore
        print(simcore.inputs)
    assert "Expecting version 0.1, found version 0.0" in str(excinfo.value)

def test_invalid_configuration(special_simcore_configuration):
    special_configuration = {"whatever":"stuff"}
    special_simcore_configuration(special_configuration)

    from .. import exceptions
    with pytest.raises(exceptions.InvalidProtocolError, message="Expecting WrongProtocol") as excinfo:
        from .. import simcore
        print(simcore.inputs)
    assert "Invalid protocol used in" in str(excinfo.value)

def test_noinputsoutputs(special_simcore_configuration):
    # create empty configuration
    special_configuration = get_empty_config()
    special_simcore_configuration(special_configuration)

    from .. import simcore
    from .. import exceptions

    assert not simcore.inputs
    assert not simcore.outputs

    with pytest.raises(exceptions.UnboundPortError, message="Expecting UnboundPortError") as excinfo:
        input0 = simcore.inputs[0]
        print(input0)
    assert "No port bound at index" in str(excinfo.value)

    with pytest.raises(exceptions.UnboundPortError, message="Expecting UnboundPortError") as excinfo:
        output0 = simcore.outputs[0]
        print(output0)
    assert "No port bound at index" in str(excinfo.value)


def update_config_file(path, config):
    import json
    with open(path, "w") as json_file:
        json.dump(config, json_file)


def test_adding_new_ports(special_simcore_configuration):
    special_configuration = get_empty_config()
    config_file = special_simcore_configuration(special_configuration)
    from .. import simcore
    # check empty configuration
    assert not simcore.inputs
    assert not simcore.outputs

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

    assert len(simcore.inputs) == 1
    assert simcore.inputs[0].key == "in_15"
    assert simcore.inputs[0].label == "additional data"
    assert simcore.inputs[0].description == "here some additional data"
    assert simcore.inputs[0].type == "int"
    assert simcore.inputs[0].value == "15"
    assert simcore.inputs[0].timestamp == "2018-05-22T19:34:53.511Z"

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
    assert len(simcore.inputs) == 1
    assert simcore.inputs[0].key == "in_15"
    assert simcore.inputs[0].label == "additional data"
    assert simcore.inputs[0].description == "here some additional data"
    assert simcore.inputs[0].type == "int"
    assert simcore.inputs[0].value == "15"
    assert simcore.inputs[0].timestamp == "2018-05-22T19:34:53.511Z"
    # new output
    assert len(simcore.outputs) == 1
    assert simcore.outputs[0].key == "out_15"
    assert simcore.outputs[0].label == "output data"
    assert simcore.outputs[0].description == "a cool output"
    assert simcore.outputs[0].type == "bool"
    assert simcore.outputs[0].value == "null"
    assert simcore.outputs[0].timestamp == "2018-05-22T19:34:53.511Z"


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
    from .. import simcore
    assert len(simcore.inputs) == 2
    assert len(simcore.outputs) == 2
    # let's remove the first input
    del special_configuration["inputs"][0]
    update_config_file(config_file, special_configuration)
    assert len(simcore.inputs) == 1
    assert len(simcore.outputs) == 2

    assert simcore.inputs[0].key == "in_17"
    assert simcore.inputs[0].label == "additional data"
    assert simcore.inputs[0].description == "here some additional data"
    assert simcore.inputs[0].type == "int"
    assert simcore.inputs[0].value == "15"
    assert simcore.inputs[0].timestamp == "2018-05-22T19:34:53.511Z"

    # let's do the same for the second output
    del special_configuration["outputs"][1]
    update_config_file(config_file, special_configuration)
    assert len(simcore.inputs) == 1
    assert len(simcore.outputs) == 1

    assert simcore.outputs[0].key == "out_15"
    assert simcore.outputs[0].label == "additional data"
    assert simcore.outputs[0].description == "here some additional data"
    assert simcore.outputs[0].type == "int"
    assert simcore.outputs[0].value == "15"
    assert simcore.outputs[0].timestamp == "2018-05-22T19:34:53.511Z"
