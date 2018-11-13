#pylint: disable=C0111
import mock
import pytest

from simcore_sdk.node_ports._data_item import DataItem
from simcore_sdk.node_ports._data_items_list import DataItemsList
from simcore_sdk.node_ports._item import Item
from simcore_sdk.node_ports._items_list import ItemsList
from simcore_sdk.node_ports._schema_item import SchemaItem
from simcore_sdk.node_ports._schema_items_list import SchemaItemsList


def create_item(key, item_type, item_value):
    return Item(SchemaItem(key=key, 
                    label="a label", 
                    description="a description", 
                    type=item_type, 
                    displayOrder=2), 
                DataItem(key=key, 
                    value=item_value))

def create_items_list(key_item_value_tuples):
    schemas = SchemaItemsList({key:SchemaItem(key=key, label="a label", description="a description", type=item_type, displayOrder=2) for (key, item_type, _) in key_item_value_tuples})
    payloads = DataItemsList({key:DataItem(key=key, value=item_value) for key,_,item_value in key_item_value_tuples})
    return ItemsList(schemas, payloads)
    

def test_default_list():
    itemslist = ItemsList(SchemaItemsList(), DataItemsList())

    assert not itemslist    
    assert not itemslist.change_notifier
    assert not itemslist.get_node_from_node_uuid_cb

def test_creating_list():
    itemslist = create_items_list([("1", "integer", 333), ("2", "integer", 333), ("3", "integer", 333)])
    assert len(itemslist) == 3

def test_accessing_by_key():
    itemslist = create_items_list([("1", "integer", 333), ("2", "integer", 333), ("3", "integer", 333)])
    assert itemslist[0].key == "1"
    assert itemslist["1"].key == "1"
    assert itemslist[1].key == "2"
    assert itemslist["2"].key == "2"
    assert itemslist[2].key == "3"
    assert itemslist["3"].key == "3"

def test_access_by_wrong_key():
    from simcore_sdk.node_ports import exceptions
    itemslist = create_items_list([("1", "integer", 333), ("2", "integer", 333), ("3", "integer", 333)])    
    with pytest.raises(exceptions.UnboundPortError, message="Expecting UnboundPortError"):
        print(itemslist["fdoiht"])

@pytest.mark.asyncio
async def test_modifying_items_triggers_cb(): #pylint: disable=C0103
    mock_method = mock.Mock()

    itemslist = create_items_list([("1", "integer", 333), ("2", "integer", 333), ("3", "integer", 333)])
    itemslist.change_notifier = mock_method
    await itemslist[0].set(-123)
    mock_method.assert_called_once()
    mock_method.reset_mock()
    await itemslist[0].set(234)
    mock_method.assert_called_once()
