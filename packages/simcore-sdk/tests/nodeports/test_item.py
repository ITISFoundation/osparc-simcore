#pylint: disable=C0111
from pathlib import Path

import pytest

from simcore_sdk.nodeports import config, exceptions
from simcore_sdk.nodeports._data_item import DataItem
from simcore_sdk.nodeports._item import Item
from simcore_sdk.nodeports._schema_item import SchemaItem


def create_item(item_type, item_value):
    key = "some key"
    return Item(SchemaItem(key=key, 
                    label="a label", 
                    description="a description", 
                    type=item_type, 
                    displayOrder=2), DataItem(key=key, 
                    value=item_value))

def test_default_item():
    with pytest.raises(exceptions.InvalidProtocolError, message="Expecting InvalidProtocolError"):
        Item(None, None)

def test_item():
    key = "my key"
    label = "my label"
    description = "my description"
    item_type = "boolean"
    item_value = True
    display_order = 2

    item = Item(SchemaItem(key=key, label=label, description=description, type=item_type, displayOrder=display_order),
            DataItem(key=key, value=item_value))

    assert item.key == key
    assert item.label == label
    assert item.description == description
    assert item.type == item_type
    assert item.value == item_value

    assert item.new_data_cb is None

    assert item.get() == item_value

def test_valid_type():
    for item_type in config.TYPE_TO_PYTHON_TYPE_MAP:
        item = create_item(item_type, None)
        assert item.get() is None

def test_invalid_type():
    item = create_item("some wrong type", None)
    with pytest.raises(exceptions.InvalidProtocolError, message="Expecting InvalidProtocolError") as excinfo:
        item.get()
    assert "Invalid protocol used" in str(excinfo.value)

def test_invalid_value_type():
    #pylint: disable=W0612
    with pytest.raises(exceptions.InvalidItemTypeError, message="Expecting InvalidItemTypeError") as excinfo:
        create_item("integer", "not an integer")

@pytest.mark.parametrize("item_type, item_value_to_set, expected_value", [
    ("integer", 26, 26),
    ("number", -746.4748, -746.4748),
    ("data:*/*", __file__, {"store":"s3-z43", "path":"undefined/undefined/{filename}".format(filename=Path(__file__).name)}),
    ("boolean", False, False),    
    ("string", "test-string", "test-string")
])
def test_set_new_value(bucket, item_type, item_value_to_set, expected_value): # pylint: disable=W0613
    import mock
    mock_method = mock.Mock()
    item = create_item(item_type, None)
    item.new_data_cb = mock_method
    assert item.get() is None
    item.set(item_value_to_set)
    mock_method.assert_called_with(DataItem(key=item.key, value=expected_value))

@pytest.mark.parametrize("item_type, item_value_to_set", [
    ("integer", -746.4748),
    ("number", "a string"),
    ("data:*/*", str(Path(__file__).parent)),
    ("boolean", 123),
    ("string", True)
])
def test_set_new_invalid_value(bucket, item_type, item_value_to_set): # pylint: disable=W0613
    item = create_item(item_type, None)
    assert item.get() is None
    with pytest.raises(exceptions.InvalidItemTypeError, message="Expecting InvalidItemTypeError") as excinfo:
        item.set(item_value_to_set)
    assert "Invalid item type" in str(excinfo.value)
