#pylint: disable=C0111
import datetime

import pytest
from pathlib import Path
from simcore_sdk.nodeports import config, exceptions
from simcore_sdk.nodeports._item import DataItem


def create_item(item_type, item_value, timestamp=None):    
    if not timestamp:
        timestamp = datetime.datetime.utcnow().isoformat()
    return DataItem(key="a key", 
                    label="a label", 
                    desc="a description", 
                    type=item_type, 
                    value=item_value, 
                    timestamp=timestamp)

def test_default_item():
    #pylint: disable=W0612
    with pytest.raises(exceptions.InvalidProtocolError, message="Expecting InvalidProtocolError") as excinfo:
        item = DataItem() 

def test_item_with_optional_timestamp():
    key = "my key"
    label = "my label"
    description = "my description"
    item_type = "bool"
    item_value = "true"
    item = DataItem(key=key, label=label, desc=description, type=item_type, value=item_value)
    assert item.key == key
    assert item.label == label
    assert item.desc == description
    assert item.type == item_type
    assert item.value == item_value

    assert item.new_data_cb is None

    assert item.get()

def test_item():
    key = "my key"
    label = "my label"
    description = "my description"
    item_type = "bool"
    item_value = "true"
    timestamp = datetime.datetime.now().isoformat()
    item = DataItem(key=key, label=label, desc=description, type=item_type, value=item_value, timestamp=timestamp)
    assert item.key == key
    assert item.label == label
    assert item.desc == description
    assert item.type == item_type
    assert item.value == item_value
    assert item.timestamp == timestamp

    assert item.new_data_cb is None

    assert item.get()

def test_valid_type():
    for item_type in config.TYPE_TO_PYTHON_TYPE_MAP:
        item = create_item(item_type, "null")
        assert item.get() is None

def test_invalid_type():
    item = create_item("some wrong type", "null")
    with pytest.raises(exceptions.InvalidProtocolError, message="Expecting InvalidProtocolError") as excinfo:
        item.get()
    assert "Invalid protocol used" in str(excinfo.value)

def test_invalid_value_type():
    item = create_item("integer", "not an integer")
    #pylint: disable=W0612
    with pytest.raises(ValueError, message="Expecting InvalidProtocolError") as excinfo:
        item.get()

@pytest.mark.parametrize("item_type, item_value_to_set, expected_value", [
    ("integer", 26, "26"),
    ("number", -746.4748, "-746.4748"),
    ("file-url", __file__, "link.undefined.a key"),
    ("bool", False, "False"),    
    ("string", "test-string", "test-string"),
    ("folder-url", str(Path(__file__).parent), "link.undefined.a key")
])
def test_set_new_value(bucket, item_type, item_value_to_set, expected_value): # pylint: disable=W0613
    import mock
    mock_method = mock.Mock()
    item = create_item(item_type, "null")
    item.new_data_cb = mock_method
    assert item.get() is None
    item.set(item_value_to_set)
    
    mock_method.assert_called_with(create_item(item_type, expected_value, mock.ANY))

@pytest.mark.parametrize("item_type, item_value_to_set", [
    ("integer", -746.4748),
    ("number", "a string"),
    ("file-url", str(Path(__file__).parent)),
    ("bool", 123),
    ("string", True),
    ("folder-url", __file__)
])
def test_set_new_invalid_value(bucket, item_type, item_value_to_set): # pylint: disable=W0613
    item = create_item(item_type, "null")
    assert item.get() is None
    with pytest.raises(exceptions.InvalidItemTypeError, message="Expecting InvalidItemTypeError") as excinfo:
        item.set(item_value_to_set)
    assert "Invalid item type" in str(excinfo.value)
    
    