"""This module defines a container for port descriptions"""

# pylint: disable=too-many-ancestors
import logging
from collections.abc import MutableSequence
from simcore_api import exceptions

_LOGGER = logging.getLogger(__name__)

class DataItemsList(MutableSequence): 
    """This class contains a list of Data Items."""

    def __init__(self, data=None, read_only=False, change_cb=None):
        _LOGGER.debug("Creating DataItemsList with %s", data)
        if data is None:
            data = []
        self.lst = data
        self.read_only = read_only
        self.__change_notifier = change_cb
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

    def __setitem__(self, index, value):
        _LOGGER.debug("Setting item %s with %s", index, value)
        if self.read_only:
            raise exceptions.ReadOnlyError(self)        
        if isinstance(index, str):
            # it might be a key            
            index = self.__find_index_from_key(index)
        self.lst[index] = value
        self.__assign_change_notifier_to_data()
        self.__notify_client()

    def __notify_client(self):
        if self.change_notifier and callable(self.change_notifier):
            self.change_notifier() #pylint: disable=not-callable

    def __getitem__(self, index):
        _LOGGER.debug("Getting item %s", index)
        if isinstance(index, str):
            # it might be a key
            index = self.__find_index_from_key(index)
        if index < len(self.lst):
            return self.lst[index]
        raise exceptions.UnboundPortError(index)

    def __len__(self):        
        return len(self.lst)

    def __delitem__(self, index):
        _LOGGER.debug("Deleting item %s", index)
        del self.lst[index]

    def insert(self, index, value):
        _LOGGER.debug("Inserting item %s at %s", value, index)
        self.lst.insert(index, value)

    def __find_index_from_key(self, item_key):
        indices = [index for index in range(0, len(self.lst)) if self.lst[index].key == item_key]
        if indices is None:
            raise exceptions.InvalidKeyError(item_key)
        if len(indices) > 1:
            raise exceptions.InvalidProtocolError(indices)
        return indices[0]

    def __assign_change_notifier_to_data(self):
        for data in self.lst:
            data.new_data_cb = self.__item_value_updated_cb

    def __item_value_updated_cb(self, new_data_item):
        # a new item shall replace the current one
        self.__replace_item(new_data_item)
        self.__notify_client()

    def __replace_item(self, new_data_item):
        item_index = self.__find_index_from_key(new_data_item.key)
        self.lst[item_index] = new_data_item
