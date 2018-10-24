import pytest

from simcore_sdk.nodeports import exceptions
from simcore_sdk.nodeports._schema_item import SchemaItem

def test_default_item():
    with pytest.raises(exceptions.InvalidProtocolError, message="Expecting InvalidProtocolError") as excinfo:
        item = SchemaItem() #pylint: disable=W0612

def test_check_item_required_fields(): #pylint: disable=W0612
    with pytest.raises(exceptions.InvalidProtocolError, message="Expecting InvalidProtocolError"):
        SchemaItem(key="a key", label="a label", description="a description")
    with pytest.raises(exceptions.InvalidProtocolError, message="Expecting InvalidProtocolError"):
        SchemaItem(label="a label", description="a description", type="a type")
    with pytest.raises(exceptions.InvalidProtocolError, message="Expecting InvalidProtocolError"):
        SchemaItem(key="a key", description="a description", type="a type")
    with pytest.raises(exceptions.InvalidProtocolError, message="Expecting InvalidProtocolError"):
        SchemaItem(key="a key", label="a label", type="a type")

    # this shall not trigger an exception
    SchemaItem(key="a key", label="a label", description="a description", type="a type")

def test_item_construction():
    item = SchemaItem(key="a key", label="a label", description="a description", type="a type")
    assert item.key == "a key"
    assert item.label == "a label"
    assert item.description == "a description"
    assert item.type == "a type"
    assert item.fileToKeyMap == None
    assert item.defaultValue == None
    assert item.widget == None