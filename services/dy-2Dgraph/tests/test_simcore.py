
#pylint: disable=W0212
#pylint: disable=C0111

def test_default_configuration():
    from simcore_api import simcore
    assert simcore.Simcore

    assert len(simcore._inputs) == 2
    assert simcore._inputs[0].key == "in_1"
    assert simcore._inputs[0].label == "computational data"
    assert simcore._inputs[0].description == "these are computed data out of a pipeline"
    assert simcore._inputs[0].type == "file-url"
    assert simcore._inputs[0].value == "/home/jovyan/data/outputControllerOut.dat"
    assert simcore._inputs[0].timestamp == "2018-05-23T15:34:53.511Z"

    assert simcore._inputs[1].key == "in_5"
    assert simcore._inputs[1].label == "some number"
    assert simcore._inputs[1].description == "numbering things"
    assert simcore._inputs[1].type == "integer"
    assert simcore._inputs[1].value == "666"
    assert simcore._inputs[1].timestamp == "2018-05-23T15:34:53.511Z"

    assert len(simcore._outputs) == 1
    assert simcore._outputs[0].key == "out_1"
    assert simcore._outputs[0].label == "some boolean output"
    assert simcore._outputs[0].description == "could be true or false..."
    assert simcore._outputs[0].type == "bool"
    assert simcore._outputs[0].value == "null"
    assert simcore._outputs[0].timestamp == "2018-05-23T15:34:53.511Z"

def test_default_json_encoding():
    from simcore_api import simcore
    from simcore_api.simcore import _SimcoreEncoder
    import json
    import os

    json_data = json.dumps(simcore, cls=_SimcoreEncoder)
    default_config_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), r"../config/connection_config.json")
    with open(default_config_path) as file:
        original_json_data = file.read()
    assert json.loads(json_data) == json.loads(original_json_data)

def test_no_inputs_outputs():
    import pytest
    import os
    import tempfile
    import json
    # create temporary json file
    temp_file = tempfile.NamedTemporaryFile()
    temp_file.close()
    # create empty configuration
    config = {
        "version":"0.1",
        "inputs": [
        ],
        "outputs": [       
        ]
    }   
    with open(temp_file.name) as fp:
        json.dump(config, fp)

    os.environ["SIMCORE_CONFIG_PATH"] = temp_file.name
    from simcore_api import simcore

    assert simcore.inputs == None
    assert simcore.outputs == None

    with pytest.raises(UnboundPortError, message="Expecting UnboundPortError") as excinfo:
        simcore.inputs[0]
    assert "Unbound port index" in str(excinfo.value)

    with pytest.raises(UnboundPortError, message="Expecting UnboundPortError") as excinfo:
        simcore.outputs[0]
    assert "Unbound port index" in str(excinfo.value)

    os.unlink(temp_file.name)
    assert os.path.exists(temp_file.name)

def test_adding_new_input():
    import os
    import tempfile

    # create temporary json file
    temp_file = tempfile.NamedTemporaryFile()

    os.environ["SIMCORE_CONFIG_PATH"] = r"C:\Users\anderegg\Desktop\alternative_config.json"
    from simcore_api import simcore