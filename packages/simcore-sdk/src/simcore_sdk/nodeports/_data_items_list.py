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

    def __init__(self, data:Dict[str, DataItem]=None):
        log.debug("Creating DataItemsList with %s", data)
        if data is None:
            data = {}
        self._store = data

    def __setitem__(self, key, value: DataItem):
        log.debug("Setting item %s with %s", key, value)
        if not isinstance(value, DataItem):
            raise TypeError
        if isinstance(key, int):
            key = self._store.keys()[key]
        
        self._store[key] = value

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
        if isinstance(key, int):
            key = self._store.keys()[key]
        if not key in self._store:
            raise exceptions.UnboundPortError(key)
        del self._store[key]
