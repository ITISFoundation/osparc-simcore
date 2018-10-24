"""This module defines a container for port descriptions"""

# pylint: disable=too-many-ancestors
import logging
from typing import Dict
from collections import MutableMapping
from simcore_sdk.nodeports import exceptions
from simcore_sdk.nodeports._data_item import DataItem

log = logging.getLogger(__name__)

class DataItemsList(MutableMapping):
    """This class contains a list of Data Items."""

    def __init__(self, data:Dict[str, DataItem]=None, 
                        read_only:bool=False, 
                        change_cb=None, 
                        get_node_from_node_uuid_cb=None):
        log.debug("Creating DataItemsList with %s", data)
        if data is None:
            data = {}

        self._store = data
        self.read_only = read_only

        self.__change_notifier = change_cb
        self.__get_node_from_node_uuid_cb = get_node_from_node_uuid_cb
        self.__assign_change_notifier_to_data()

    @property
    def change_notifier(self):
        """Callback function to be set if client code wants notifications when
        an item is modified or replaced"""
        return self.__change_notifier

    @change_notifier.setter
    def change_notifier(self, value):
        self.__change_notifier = value
        self.__assign_change_notifier_to_data()

    @property
    def get_node_from_node_uuid_cb(self):
        return self.__get_node_from_node_uuid_cb

    @get_node_from_node_uuid_cb.setter
    def get_node_from_node_uuid_cb(self, value):
        self.__get_node_from_node_uuid_cb = value
        self.__assign_change_notifier_to_data()

    def __setitem__(self, key, value: DataItem):
        log.debug("Setting item %s with %s", key, value)
        if self.read_only:
            raise exceptions.ReadOnlyError(self)
        if not isinstance(value, DataItem):
            raise TypeError
        if isinstance(key, int):
            key = self._store.keys()[key]
        if not key in self._store:
            raise exceptions.UnboundPortError(key)
        
        self._store[key] = value
        self.__assign_change_notifier_to_data()
        self.__notify_client()


    def __notify_client(self):
        if self.change_notifier and callable(self.change_notifier):
            self.change_notifier() #pylint: disable=not-callable

    def __getitem__(self, key):
        log.debug("Getting item %s", key)
        if isinstance(key, int):
            if key < len(self._store):
                key = self._store.keys()[key]
        if not key in self._store:
            raise exceptions.UnboundPortError(key)
        return self._store[key]
        
    def __iter__(self):
        return iter(self._store)

    def __len__(self):
        return len(self._store)

    def __delitem__(self, key):
        log.debug("Deleting item %s", key)
        if self.read_only:
            raise exceptions.ReadOnlyError(self)
        if isinstance(key, int):
            key = self._store.keys()[key]
        if not key in self._store:
            raise exceptions.UnboundPortError(key)
        del self._store[key]

    def __assign_change_notifier_to_data(self):
        for _, data in self._store.items():
            data.new_data_cb = self.__item_value_updated_cb
            data.get_node_from_uuid_cb = self.get_node_from_node_uuid_cb

    def __item_value_updated_cb(self, new_data_item):
        # a new item shall replace the current one
        self.__replace_item(new_data_item)
        self.__notify_client()

    def __replace_item(self, new_data_item):
        self._store[new_data_item.key] = new_data_item
