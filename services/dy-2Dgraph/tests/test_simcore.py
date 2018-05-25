
import simcore_api
import datetime

def import_simcore_api():
    from simcore_api import simcore
    assert(simcore.Simcore)

def test_input1():
    from simcore_api import simcore
    assert(simcore.input1.type == "file")
    assert(simcore.input1.format == "csv")
    assert(simcore.input1.value == "test.csv")
    assert(simcore.input1.label == "computational data")
    assert(simcore.input1.timestamp.isoformat(timespec='milliseconds').replace("+00:00","Z") == "2018-05-23T15:34:51.511Z")

def test_input4():
    from simcore_api import simcore
    assert(simcore.input4.type == "int")
    assert(simcore.input4.value == "666")
    assert(simcore.input4.label == "some number")
    assert(simcore.input4.timestamp.isoformat(timespec='milliseconds').replace("+00:00","Z") == "2018-05-23T15:34:51.511Z")

def test_output1():
    from simcore_api import simcore
    assert(simcore.output1.type == "bool")
    assert(simcore.output1.value == "none")
    assert(simcore.output1.label == "some boolean output")
    assert(simcore.output1.timestamp.isoformat(timespec='milliseconds').replace("+00:00","Z") == "2018-05-23T15:34:51.511Z")