#pylint: disable=C0111
import datetime

import pytest

from simcore_sdk.nodeports._item import DataItem
from simcore_sdk.nodeports._itemslist import DataItemsList


def create_item(key, item_type, item_value, timestamp=None):    
    if not timestamp:
        timestamp = datetime.datetime.utcnow().isoformat()
    return DataItem(key=key, 
                    label="a label", 
                    desc="a description", 
                    type=item_type, 
                    value=item_value, 
                    timestamp=timestamp)

def test_default_list():
    itemslist = DataItemsList()

    assert not itemslist
    assert not itemslist.read_only
    assert itemslist.change_notifier is None

def test_reject_items_with_same_key():
    from simcore_sdk.nodeports import exceptions
    with pytest.raises(exceptions.InvalidProtocolError, message="Expecting InvalidProtocolError"):
        DataItemsList([create_item("1", "integer", "333"), create_item("1", "integer", "444"), create_item("3", "integer", "333")])
    
    itemslist = DataItemsList()
    with pytest.raises(exceptions.InvalidProtocolError, message="Expecting InvalidProtocolError"):
        itemslist.insert(0, create_item("4", "integer", "333"))
        itemslist.insert(0, create_item("5", "integer", "333"))
        itemslist.insert(0, create_item("5", "integer", "333"))

    itemslist = DataItemsList([create_item("1", "integer", "333"), create_item("2", "integer", "444"), create_item("3", "integer", "333")])
    with pytest.raises(exceptions.InvalidProtocolError, message="Expecting InvalidProtocolError"):
        itemslist[1] = create_item("1", "integer", "333")

    with pytest.raises(AttributeError, message="Expecting AttributeError"):
        itemslist[1].key = "1"
    

def test_adding_removing_items():
    itemslist = DataItemsList([create_item("1", "integer", "333"), create_item("2", "integer", "333"), create_item("3", "integer", "333")])

    assert len(itemslist) == 3
    itemslist.insert(0, create_item("4", "integer", "333"))
    itemslist.insert(0, create_item("5", "integer", "333"))
    itemslist.insert(0, create_item("6", "integer", "333"))
    
    del itemslist[1]
    assert len(itemslist) == 5

def test_accessing_by_key():
    itemslist = DataItemsList([create_item("1", "integer", "333"), create_item("2", "integer", "333"), create_item("3", "integer", "333")])
    for item in itemslist:
        assert itemslist[item.key] == item

def test_access_by_wrong_key():
    from simcore_sdk.nodeports import exceptions
    itemslist = DataItemsList([create_item("1", "integer", "333"), create_item("2", "integer", "333"), create_item("3", "integer", "333")], read_only=True)    
    with pytest.raises(exceptions.UnboundPortError, message="Expecting UnboundPortError"):
        print(itemslist["fdoiht"])


def test_adding_bad_items():
    with pytest.raises(TypeError, message="Expecting TypeError"):
        itemslist = DataItemsList([4, 54, "fdoiht"])
    itemslist = DataItemsList()
    assert not itemslist
    with pytest.raises(TypeError, message="Expecting TypeError"):
        itemslist.insert(0, 23)    
    with pytest.raises(TypeError, message="Expecting TypeError"):
        itemslist.insert(0, 455)
    with pytest.raises(TypeError, message="Expecting TypeError"):
        itemslist.insert(0, "blahblah")

def test_read_only():
    from simcore_sdk.nodeports import exceptions
    itemslist = DataItemsList([create_item("1", "integer", "333"), create_item("2", "integer", "333"), create_item("3", "integer", "333")], read_only=True)    
    assert len(itemslist) == 3
    
    with pytest.raises(exceptions.ReadOnlyError, message="Expecting ReadOnlyError") as excinfo:
        itemslist.insert(0, create_item("10", "integer", "333"))
    assert "Trying to modify read-only object" in str(excinfo.value)

    with pytest.raises(exceptions.ReadOnlyError, message="Expecting ReadOnlyError") as excinfo:
        itemslist[1] = create_item("11", "integer", "222")
    assert "Trying to modify read-only object" in str(excinfo.value)

    with pytest.raises(exceptions.ReadOnlyError, message="Expecting ReadOnlyError") as excinfo:
        del itemslist[1]
    assert "Trying to modify read-only object" in str(excinfo.value)


def test_modifying_items_triggers_cb(): #pylint: disable=C0103
    import mock
    mock_method = mock.Mock()

    itemslist = DataItemsList([create_item("1", "integer", "333"), create_item("2", "integer", "333"), create_item("3", "integer", "333")], change_cb=mock_method)    
    itemslist.insert(0, create_item("10", "integer", "333"))
    mock_method.assert_called_once()
    mock_method.reset_mock()
    itemslist[0] = create_item("10", "integer", "4444")
    mock_method.assert_called_once()
    mock_method.reset_mock()
    itemslist[0].set(234)
    mock_method.assert_called_once()

def test_modifying_item_changes_timestamp(): #pylint: disable=C0103
    import dateutil.parser
    import time
    itemslist = DataItemsList([create_item("1", "integer", "333"), create_item("2", "integer", "333"), create_item("3", "integer", "333")])
    original_timestamp = dateutil.parser.parse(itemslist[0].timestamp)
    time.sleep(0.1)
    itemslist[0].set(47475)
    new_timestamp = dateutil.parser.parse(itemslist[0].timestamp)
    assert new_timestamp > original_timestamp
