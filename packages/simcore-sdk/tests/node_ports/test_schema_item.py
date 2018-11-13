import pytest
from copy import deepcopy
from simcore_sdk.node_ports import exceptions, config
from simcore_sdk.node_ports._schema_item import SchemaItem

def test_default_item():
    with pytest.raises(exceptions.InvalidProtocolError, message="Expecting InvalidProtocolError"):
        item = SchemaItem() #pylint: disable=W0612

def test_check_item_required_fields(): #pylint: disable=W0612
    required_parameters = {key:"defaultValue" for key, required in config.SCHEMA_ITEM_KEYS.items() if required}
    # this shall not trigger an exception
    SchemaItem(**required_parameters)

    for key in required_parameters:
        parameters = deepcopy(required_parameters)
        parameters.pop(key)
        with pytest.raises(exceptions.InvalidProtocolError, message="Expecting InvalidProtocolError"):
            SchemaItem(**parameters)

def test_item_construction_default():
    item = SchemaItem(key="a key", label="a label", description="a description", type="a type", displayOrder=2)
    assert item.key == "a key"
    assert item.label == "a label"
    assert item.description == "a description"
    assert item.type == "a type"
    assert item.displayOrder == 2
    assert item.fileToKeyMap == None
    assert item.defaultValue == None
    assert item.widget == None

def test_item_construction_with_optional_params():
    item = SchemaItem(key="a key", label="a label", description="a description", type="a type", displayOrder=2, fileToKeyMap={"file1.txt":"a key"}, defaultValue="some value", widget={})
    assert item.key == "a key"
    assert item.label == "a label"
    assert item.description == "a description"
    assert item.type == "a type"
    assert item.displayOrder == 2
    assert item.fileToKeyMap == {"file1.txt":"a key"}
    assert item.defaultValue == "some value"
    assert item.widget == {}