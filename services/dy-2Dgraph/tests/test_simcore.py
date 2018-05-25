
import pytest
import simcore_api
import datetime

def import_simcore_api():
    from simcore_api import simcore
    assert(simcore.Simcore)
    assert(len(simcore.inputs) == 2)

def test_input1():
    from simcore_api import simcore
    assert(simcore.inputs[0].key == "in_1")
    assert(simcore.inputs[0].label == "computational data")
    assert(simcore.inputs[0].desc == "these are computed data out of a pipeline")
    assert(simcore.inputs[0].type == "file-url")
    assert(simcore.inputs[0].value == "test.csv")
    assert(simcore.inputs[0].timestamp.isoformat(timespec='milliseconds').replace("+00:00","Z") == "2018-05-23T15:34:53.511Z")

def test_input4():
    from simcore_api import simcore
    assert(simcore.inputs[1].key == "in_5")
    assert(simcore.inputs[1].label == "hell")
    assert(simcore.inputs[1].desc == "the beast")
    assert(simcore.inputs[1].type == "integer")
    assert(simcore.inputs[1].value == "666")
    assert(simcore.inputs[1].timestamp.isoformat(timespec='milliseconds').replace("+00:00","Z") == "2018-05-23T15:34:53.511Z")

def test_output1():
    from simcore_api import simcore
    assert(simcore.outputs[0].key == "out_1")
    assert(simcore.outputs[0].type == "bool")
    assert(simcore.outputs[0].value == "null")
    assert(simcore.outputs[0].label == "some boolean output")
    assert(simcore.outputs[0].timestamp.isoformat(timespec='milliseconds').replace("+00:00","Z") == "2018-05-23T15:34:53.511Z")