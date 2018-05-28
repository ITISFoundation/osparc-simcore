
#pylint: disable=W0212
#pylint: disable=C0111

def import_simcore_api():
    from simcore_api import simcore
    assert simcore.Simcore

def test_default_configuration():
    from simcore_api import simcore
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

def test_default_json_decoding():
    from simcore_api import simcore
    from simcore_api.simcore import _SimcoreEncoder
    import json
    import os

    json_data = json.dumps(simcore, cls=_SimcoreEncoder)
    default_config_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), r"../config/connection_config.json")
    with open(default_config_path) as file:
        original_json_data = file.read()
    assert json.loads(json_data) == json.loads(original_json_data)
