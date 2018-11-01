"""This module contains an item representing a node port"""

import collections
import datetime
import logging
import os
from pathlib import Path

from simcore_sdk.nodeports import config, exceptions, filemanager

log = logging.getLogger(__name__)

_DataItem = collections.namedtuple("_DataItem", config.DATA_ITEM_KEYS)

def is_value_link(value):
    return isinstance(value, str) and value.startswith(config.LINK_PREFIX)

def decode_link(encoded_link):
    link = encoded_link.split(".")
    if len(link) < 3:
        raise exceptions.InvalidProtocolError(encoded_link, "Invalid link definition: " + str(encoded_link))
    other_node_uuid = link[1]
    other_port_key = ".".join(link[2:])
    return other_node_uuid, other_port_key

def encode_link(node_uuid: str, link_value: str):
    return config.LINK_PREFIX + str(node_uuid) + "." + link_value

class DataItem(_DataItem):
    """This class encapsulate a Data Item and provide accessors functions"""
    def __new__(cls, **kwargs):
        new_kargs = dict.fromkeys(config.DATA_ITEM_KEYS)
        new_kargs['timestamp'] = datetime.datetime.now().isoformat()
        for key in config.DATA_ITEM_KEYS:
            if key not in kwargs:
                if key != "timestamp":
                    raise exceptions.InvalidProtocolError(kwargs, "key \"%s\" is missing" % (str(key)))
            else:
                new_kargs[key] = kwargs[key]

        log.debug("Creating new data item with %s", new_kargs)
        self = super(DataItem, cls).__new__(cls, **new_kargs)
        return self

    def __init__(self, **_kwargs):
        super(DataItem, self).__init__()
        self.new_data_cb = None
        self.get_node_from_uuid_cb = None

    def get(self):
        """returns the data converted to the underlying type.

            Can throw InvalidPtrotocolError if the underling type is unknown.
            Can throw ValueError if the conversion fails.
            returns the converted value or None if no value is defined
        """
        log.debug("Getting data item")
        if self.type not in config.TYPE_TO_PYTHON_TYPE_MAP:
            raise exceptions.InvalidProtocolError(self.type)
        if self.value == "null":
            log.debug("Got empty data item")
            return None
        log.debug("Got data item with value %s", self.value)

        if is_value_link(self.value):
            return config.TYPE_TO_PYTHON_TYPE_MAP[self.type]["type"](self.__get_value_from_link())
        # the value is not a link, let's directly convert it to the right type
        return config.TYPE_TO_PYTHON_TYPE_MAP[self.type]["type"](config.TYPE_TO_PYTHON_TYPE_MAP[self.type]["converter"](self.value))

    def set(self, value):
        """sets the data to the underlying port

        Arguments:
            value {any type} -- must be convertible to a string, or an exception will be thrown.
        """
        log.info("Setting data item with value %s", value)
        # let's create a new data if necessary
        data_dct = self._asdict()
        # try to guess the type and check the type set fits this (there can be more than one possibility, e.g. string)
        possible_types = [key for key,key_type in config.TYPE_TO_PYTHON_TYPE_MAP.items() if isinstance(value, key_type["type"])]
        log.debug("possible types are for value %s are %s", value, possible_types)
        if not self.type in possible_types:
            raise exceptions.InvalidItemTypeError(self.type, value)

        # convert to string now
        new_value = str(value)

        if self.type in config.TYPE_TO_S3_FILE_LIST:
            file_path = Path(new_value)
            if not file_path.exists() or not file_path.is_file():
                raise exceptions.InvalidItemTypeError(self.type, value)
            node_uuid = os.environ.get('SIMCORE_NODE_UUID', default="undefined")
            log.debug("file path %s will be uploaded to s3", value)
            filemanager.upload_file_to_s3(node_uuid=node_uuid, node_key=file_path.name, file_path=file_path)
            log.debug("file path %s uploaded to s3 from node %s and key %s", value, node_uuid, self.key)
            new_value = encode_link(node_uuid=node_uuid, link_value=file_path.name)

        elif self.type in config.TYPE_TO_S3_FOLDER_LIST:
            folder_path = Path(new_value)
            if not folder_path.exists() or not folder_path.is_dir():
                raise exceptions.InvalidItemTypeError(self.type, value)
            node_uuid = os.environ.get('SIMCORE_NODE_UUID', default="undefined")
            log.debug("folder %s will be uploaded to s3", value)
            filemanager.upload_folder_to_s3(node_uuid=node_uuid, node_key=folder_path.name, folder_path=folder_path)
            log.debug("folder %s uploaded to s3 from node %s and key %s", value, node_uuid, self.key)
            new_value = encode_link(node_uuid=node_uuid, link_value=folder_path.name)

        data_dct["value"] = new_value
        data_dct["timestamp"] = datetime.datetime.utcnow().isoformat()
        new_data = DataItem(**data_dct)
        if self.new_data_cb:
            log.debug("calling new data callback to update database")
            self.new_data_cb(new_data) #pylint: disable=not-callable
            log.debug("database updated")



    def __get_value_from_link(self):    # pylint: disable=R1710
        node_uuid, s3_object_name = decode_link(self.value)

        try: 
            if self.type in config.TYPE_TO_S3_FILE_LIST:
                # try to fetch from S3 as a file
                log.debug("Fetch file from S3 %s", self.value)
                
                return filemanager.download_file_from_S3(node_uuid=node_uuid,            
                                                            s3_object_name=s3_object_name,
                                                            node_key=self.key,
                                                            file_name=s3_object_name)
            if self.type in config.TYPE_TO_S3_FOLDER_LIST:
                # try to fetch from S3 as a folder
                log.debug("Fetch folder from S3 %s", self.value)
                return filemanager.download_folder_from_s3(node_uuid=node_uuid,
                                                            node_key=s3_object_name,
                                                            folder_name=self.key)
        except exceptions.S3InvalidPathError as err:
            # the file was not found, maybe it is written as node_uuid.port_key instead of node_uuid.s3_object_name?
            log.info("The file/folder was not found on S3, maybe it is written as node_uuid.port_key instead of node_uuid.s3_object?")
            log.info("Trying now to follow node_uuid.port_key instead...")
            try:
                # try to fetch link from database node
                log.debug("Fetch value from other node %s", self.value)
                if not self.get_node_from_uuid_cb:
                    raise exceptions.NodeportsException("callback to get other node information is not set")

                other_nodeports = self.get_node_from_uuid_cb(node_uuid) #pylint: disable=not-callable
                log.debug("Received node from DB %s, now returning value", other_nodeports)
                return other_nodeports.get(s3_object_name)
            except Exception:                
                raise err from None
