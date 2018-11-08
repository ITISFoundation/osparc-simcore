import logging
from collections import Sequence

from . import exceptions
from ._data_items_list import DataItemsList
from ._item import Item
from ._schema_items_list import SchemaItemsList

log = logging.getLogger(__name__)

class ItemsList(Sequence):

    def __init__(self, schemas: SchemaItemsList, payloads: DataItemsList, 
                    change_cb=None, 
                    get_node_from_node_uuid_cb=None):
        self._schemas = schemas
        self._payloads = payloads        

        self._change_notifier = change_cb
        self._get_node_from_node_uuid_cb = get_node_from_node_uuid_cb
    
    def __getitem__(self, key)->Item:
        schema = self._schemas[key]
        try:
            payload = self._payloads[schema.key]
        except exceptions.InvalidKeyError:
            # there is no payload
            payload = None
        except exceptions.UnboundPortError:            
            payload = None
        item = Item(schema, payload)
        item.new_data_cb = self.__item_value_updated_cb
        item.get_node_from_uuid_cb = self.get_node_from_node_uuid_cb
        return item

    def __len__(self):
        return len(self._schemas)

    @property
    def change_notifier(self):
        """Callback function to be set if client code wants notifications when
        an item is modified or replaced"""
        return self._change_notifier

    @change_notifier.setter
    def change_notifier(self, value):
        self._change_notifier = value
    
    @property
    def get_node_from_node_uuid_cb(self):
        return self._get_node_from_node_uuid_cb

    @get_node_from_node_uuid_cb.setter
    def get_node_from_node_uuid_cb(self, value):
        self._get_node_from_node_uuid_cb = value

    def __item_value_updated_cb(self, new_data_item):
        # a new item shall replace the current one
        self.__replace_item(new_data_item)
        self.__notify_client()

    def __replace_item(self, new_data_item):
        self._payloads[new_data_item.key] = new_data_item

    def __notify_client(self):
        if self.change_notifier and callable(self.change_notifier):
            self.change_notifier() #pylint: disable=not-callable
