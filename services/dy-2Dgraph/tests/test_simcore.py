
import pytest
import simcore_api
import datetime

def import_simcore_api():
    from simcore_api import simcore
    assert(simcore.Simcore)
    assert(len(simcore._inputs) == 2)

def test_input1():
    from simcore_api import simcore
    assert(simcore._inputs[0].key == "in_1")
    assert(simcore._inputs[0].label == "computational data")
    assert(simcore._inputs[0].description == "these are computed data out of a pipeline")
    assert(simcore._inputs[0].type == "file-url")
    assert(simcore._inputs[0].value == "/home/jovyan/data/outputControllerOut.dat")
    assert(simcore._inputs[0].timestamp == "2018-05-23T15:34:53.511Z")

def test_input4():
    from simcore_api import simcore
    assert(simcore._inputs[1].key == "in_5")
    assert(simcore._inputs[1].label == "some number")
    assert(simcore._inputs[1].description == "numbering things")
    assert(simcore._inputs[1].type == "integer")
    assert(simcore._inputs[1].value == "666")
    assert(simcore._inputs[1].timestamp == "2018-05-23T15:34:53.511Z")

def test_output1():
    from simcore_api import simcore
    assert(simcore._outputs[0].key == "out_1")
    assert(simcore._outputs[0].type == "bool")
    assert(simcore._outputs[0].value == "null")
    assert(simcore._outputs[0].label == "some boolean output")
    assert(simcore._outputs[0].timestamp == "2018-05-23T15:34:53.511Z")