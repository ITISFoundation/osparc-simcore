# pylint: disable=W0613, W0621, C0111
import pytest
from pathlib import Path

def test_default_json_decoding(default_nodeports_configuration):
    from simcore_sdk.nodeports.nodeports import PORTS

    assert len(PORTS.inputs) == 2
    assert PORTS.inputs[0].key == "in_1"
    assert PORTS.inputs[0].displayOrder == 0
    assert PORTS.inputs[0].label == "computational data"
    assert PORTS.inputs[0].description == "these are computed data out of a pipeline"
    assert PORTS.inputs[0].type == "data:*/*"
    assert PORTS.inputs[0].defaultValue == None
    assert PORTS.inputs[0].fileToKeyMap == {"input1.txt":"in_1"}
    assert PORTS.inputs[0].value == {
            "nodeUuid":"456465-45ffd",
            "output": "outFile"
        }

    assert PORTS.inputs[1].key == "in_5"
    assert PORTS.inputs[1].displayOrder == 2
    assert PORTS.inputs[1].label == "some number"
    assert PORTS.inputs[1].description == "numbering things"
    assert PORTS.inputs[1].type == "integer"
    assert PORTS.inputs[1].value == 666

    assert len(PORTS.outputs) == 2
    assert PORTS.outputs[0].key == "out_1"
    assert PORTS.outputs[0].displayOrder == 0
    assert PORTS.outputs[0].label == "some boolean output"
    assert PORTS.outputs[0].description == "could be true or false..."
    assert PORTS.outputs[0].type == "boolean"
    assert PORTS.outputs[0].value == False

    assert PORTS.outputs[1].key == "out_2"
    assert PORTS.outputs[1].displayOrder == 1
    assert PORTS.outputs[1].label == "some file output"
    assert PORTS.outputs[1].description == "could be anything..."
    assert PORTS.outputs[1].type == "data:*/*"
    assert PORTS.outputs[1].value == {
            "store":"z43-s3",
            "path": "/simcore/outputControllerOut.dat"
        }

def test_default_json_encoding(default_nodeports_configuration, test_configuration_file): 
    from simcore_sdk.nodeports.nodeports import PORTS
    from simcore_sdk.nodeports.serialization import _NodeportsEncoder
    import json

    json_data = json.dumps(PORTS, cls=_NodeportsEncoder)
    original_json_data = test_configuration_file.read_text()
    
    assert json.loads(json_data) == json.loads(original_json_data)

def test_noinputsoutputs(special_nodeports_configuration):
    # create empty configuration
    import helpers
    special_configuration = helpers.get_empty_config() #pylint: disable=E1101
    special_nodeports_configuration(special_configuration)
    from simcore_sdk.nodeports.nodeports import PORTS
    from simcore_sdk.nodeports import exceptions

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
