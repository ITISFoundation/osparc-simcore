"""This module contains an item representing a node port"""

import logging
import collections
from simcore_api import exceptions
from simcore_api import config

_LOGGER = logging.getLogger(__name__)

_DataItem = collections.namedtuple("_DataItem", config.DATA_ITEM_KEYS)

class DataItem(_DataItem):
    """This class encapsulate a Data Item and provide accessors functions"""
    def __new__(cls, new_data_cb=None, **kwargs):        
        _LOGGER.debug("Creating new data item with %s", kwargs)
        self = super(DataItem, cls).__new__(cls, **kwargs)
        self.new_data_cb = new_data_cb
        return self

    def get(self):
        """returns the data converted to the underlying type.

            Can throw InvalidPtrotocolError if the underling type is unknown.
            Can throw TypeError if the conversion fails.
            returns the converted value or None if no value is defined
        """
        _LOGGER.debug("Getting data item")
        if self.type not in config.TYPE_TO_PYTHON_TYPE_MAP:
            raise exceptions.InvalidProtocolError(self.type)
        if self.value == "null":
            return None
        _LOGGER.debug("Got data item with value %s", self.value)
        return config.TYPE_TO_PYTHON_TYPE_MAP[self.type](self.value)

    def set(self, value):
        """sets the data to the underlying port
        
        Arguments:
            value {any type} -- must be convertible to a string, or an exception will be thrown.
        """
        _LOGGER.info("Setting data item with value %s", value)
        # let's create a new data
        data_dct = self._asdict()
        new_value = str(value)
        if new_value != data_dct["value"]:
            data_dct["value"] = str(value)
            new_data = DataItem(**data_dct)
            if self.new_data_cb:
                _LOGGER.debug("calling new data callback")
                self.new_data_cb(new_data) #pylint: disable=not-callable
