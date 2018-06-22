#pylint: disable=C0111
import datetime

import pytest

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
    with pytest.raises(TypeError, message="Expecting TypeError") as excinfo:
        item = DataItem() 

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
    item = create_item("int", "not an integer")
    #pylint: disable=W0612
    with pytest.raises(ValueError, message="Expecting InvalidProtocolError") as excinfo:
        item.get()
    
def test_set_new_value():
    import mock
    mock_method = mock.Mock()
    item = create_item("int", "null")
    item.new_data_cb = mock_method
    assert item.get() is None
    item.set(26)
    
    mock_method.assert_called_with(create_item("int", "26", mock.ANY))
