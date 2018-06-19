"""This module contains an item representing a node port"""

import logging
import collections
import datetime
from simcore_sdk.nodeports import exceptions
from simcore_sdk.nodeports import config
from simcore_sdk.nodeports import filemanager

_LOGGER = logging.getLogger(__name__)

_DataItem = collections.namedtuple("_DataItem", config.DATA_ITEM_KEYS)

class DataItem(_DataItem):
    """This class encapsulate a Data Item and provide accessors functions"""
    def __new__(cls, **kwargs):        
        _LOGGER.debug("Creating new data item with %s", kwargs)
        self = super(DataItem, cls).__new__(cls, **kwargs)
        self.new_data_cb = None
        self.get_node_from_uuid_cb = None
        return self

    def get(self):
        """returns the data converted to the underlying type.

            Can throw InvalidPtrotocolError if the underling type is unknown.
            Can throw ValueError if the conversion fails.
            returns the converted value or None if no value is defined
        """
        _LOGGER.debug("Getting data item")
        if self.type not in config.TYPE_TO_PYTHON_TYPE_MAP:
            raise exceptions.InvalidProtocolError(self.type)
        if self.value == "null":
            _LOGGER.debug("Got empty data item")
            return None
        _LOGGER.debug("Got data item with value %s", self.value)

        if isinstance(self.value, str) and self.value.startswith("link."):
            link = self.value.split(".")
            if len(link) != 3:
                raise exceptions.InvalidProtocolError(self.value, "Invalid link definition: " + str(self.value))
            if self.type in config.TYPE_TO_S3_LIST:
                # try to fetch from S3
                _LOGGER.debug("Fetch value from S3 %s", self.value)
                s3_link = link[1:]
                return filemanager.download_from_S3_if_newer(s3_link, self.timestamp, self.key)
            else:
                # try to fetch link from database node
                _LOGGER.debug("Fetch value from other node %s", self.value)
                
                other_node_uuid = link[1]
                other_port_key = link[2]

                if not self.get_node_from_uuid_cb:
                    raise exceptions.NodeportsException("callback to get other node information is not set")

                other_nodeports = self.get_node_from_uuid_cb(other_node_uuid) #pylint: disable=not-callable
                _LOGGER.debug("Received node from DB %s, now returning value", other_nodeports)
                return other_nodeports.get(other_port_key)


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
            data_dct["timestamp"] = datetime.datetime.utcnow().isoformat()
            new_data = DataItem(**data_dct)
            if self.new_data_cb:
                _LOGGER.debug("calling new data callback")
                self.new_data_cb(new_data) #pylint: disable=not-callable
