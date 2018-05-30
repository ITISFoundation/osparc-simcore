
#pylint: disable=W0212
#pylint: disable=C0111
import pytest


def test_default_configuration():
    from simcore_api import simcore

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
    from simcore_api import simcore
    from simcore_api.simcore import _SimcoreEncoder
    import json
    import os

    json_data = json.dumps(simcore, cls=_SimcoreEncoder)
    default_config_path = os.path.join(os.path.dirname(
        os.path.realpath(__file__)), r"../config/connection_config.json")
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
    return create_special_config

#pylint: disable=w0621
def test_noinputsoutputs(special_simcore_configuration):
    # create empty configuration
    special_configuration = {
        "version": "0.1",
        "inputs": [
        ],
        "outputs": [
        ]
    }
    special_simcore_configuration(special_configuration)

    from simcore_api import simcore
    from simcore_api import exceptions

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


def test_adding_new_input():
    import os
    import tempfile

    # create temporary json file
    temp_file = tempfile.NamedTemporaryFile()

    os.environ["SIMCORE_CONFIG_PATH"] = r"C:\Users\anderegg\Desktop\alternative_config.json"
    from simcore_api import simcore
