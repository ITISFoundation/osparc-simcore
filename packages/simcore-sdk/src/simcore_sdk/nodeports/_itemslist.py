"""This module defines a container for port descriptions"""

# pylint: disable=too-many-ancestors
import logging
from collections import MutableSequence
from simcore_sdk.nodeports import exceptions
from simcore_sdk.nodeports._item import DataItem

log = logging.getLogger(__name__)

class DataItemsList(MutableSequence):
    """This class contains a list of Data Items."""

    def __init__(self, data=None, read_only=False, change_cb=None, get_node_from_node_uuid_cb=None):
        log.debug("Creating DataItemsList with %s", data)
        if data is None:
            data = []

        data_keys = set()
        for item in data:
            if not isinstance(item, DataItem):
                raise TypeError
            data_keys.add(item.key)
        # check uniqueness... we could use directly a set for this as well
        if len(data_keys) != len(data):
            raise exceptions.InvalidProtocolError(data)
        self.__lst = data
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

    def __setitem__(self, index, value):
        log.debug("Setting item %s with %s", index, value)
        if self.read_only:
            raise exceptions.ReadOnlyError(self)
        if not isinstance(value, DataItem):
            raise TypeError
        if isinstance(index, str):
            # it might be a key
            index = self.__find_index_from_key(index)
        if not index < len(self.__lst):
            raise exceptions.UnboundPortError(index)
        # check for uniqueness
        stored_index = self.__find_index_from_key(value.key)
        if stored_index != index:
            # not the same key not allowed
            raise exceptions.InvalidProtocolError(value._asdict())
        self.__lst[index] = value
        self.__assign_change_notifier_to_data()
        self.__notify_client()


    def __notify_client(self):
        if self.change_notifier and callable(self.change_notifier):
            self.change_notifier() #pylint: disable=not-callable

    def __getitem__(self, index):
        log.debug("Getting item %s", index)
        if isinstance(index, str):
            # it might be a key
            index = self.__find_index_from_key(index)
        if index < len(self.__lst):
            return self.__lst[index]
        raise exceptions.UnboundPortError(index)

    def __len__(self):
        return len(self.__lst)

    def __delitem__(self, index):
        log.debug("Deleting item %s", index)
        if self.read_only:
            raise exceptions.ReadOnlyError(self)
        del self.__lst[index]

    def insert(self, index, value):
        log.debug("Inserting item %s at %s", value, index)
        if self.read_only:
            raise exceptions.ReadOnlyError(self)
        if not isinstance(value, DataItem):
            raise TypeError
        if self.__find_index_from_key(value.key) < len(self.__lst):
            # the key already exists
            raise exceptions.InvalidProtocolError(value._asdict())
        self.__lst.insert(index, value)
        self.__assign_change_notifier_to_data()
        self.__notify_client()

    def __find_index_from_key(self, item_key):
        indices = [index for index in range(0, len(self.__lst)) if self.__lst[index].key == item_key]
        if not indices:
            return len(self.__lst)
        if len(indices) > 1:
            raise exceptions.InvalidProtocolError(indices)
        return indices[0]

    def __assign_change_notifier_to_data(self):
        for data in self.__lst:
            data.new_data_cb = self.__item_value_updated_cb
            data.get_node_from_uuid_cb = self.get_node_from_node_uuid_cb

    def __item_value_updated_cb(self, new_data_item):
        # a new item shall replace the current one
        self.__replace_item(new_data_item)
        self.__notify_client()

    def __replace_item(self, new_data_item):
        item_index = self.__find_index_from_key(new_data_item.key)
        self.__lst[item_index] = new_data_item
