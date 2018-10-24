import logging
import os
from pathlib import Path

from . import config, exceptions, data_items_utils, filemanager
from ._data_item import DataItem
from ._schema_item import SchemaItem

log = logging.getLogger(__name__)

def _check_type(item_type, value):
    if not value:
        return
    if data_items_utils.is_value_link(value):
        return
    
    possible_types = [key for key,key_type in config.TYPE_TO_PYTHON_TYPE_MAP.items() if isinstance(value, key_type["type"])]
    if not item_type in possible_types:
        if str(item_type).startswith(config.FILE_TYPE_PREFIX) and data_items_utils.is_value_on_store(value):
            return
        raise exceptions.InvalidItemTypeError(item_type, value)

class Item():
    def __init__(self, schema:SchemaItem, data:DataItem):
        if not schema:
            raise exceptions.InvalidProtocolError(None, msg="empty schema or payload")
        self._schema = schema
        self._data = data
        self.new_data_cb = None
        self.get_node_from_uuid_cb = None

        _check_type(self.type, self.value)

    def __getattr__(self, name):
        if hasattr(self._schema, name):
            return getattr(self._schema, name)
        if hasattr(self._data, name):
            return getattr(self._data, name)

        if "value" in name and not self._data:
            if hasattr(self._schema, "defaultValue"):
                return getattr(self._schema, "defaultValue")
            return None
        raise AttributeError

    def get(self):
        """returns the data converted to the underlying type.

            Can throw InvalidPtrotocolError if the underling type is unknown.
            Can throw ValueError if the conversion fails.
            returns the converted value or None if no value is defined
        """
        log.debug("Getting item %s", self.key)
        if self.type not in config.TYPE_TO_PYTHON_TYPE_MAP and not str(self.type).startswith(config.FILE_TYPE_PREFIX):
            raise exceptions.InvalidProtocolError(self.type)
        if self.value is None:
            log.debug("Got empty data item")
            return None
        log.debug("Got data item with value %s", self.value)

        if data_items_utils.is_value_link(self.value):
            return self.__get_value_from_link(self.value)
            # return config.TYPE_TO_PYTHON_TYPE_MAP[self.type]["type"](self.__get_value_from_link())
        if data_items_utils.is_value_on_store(self.value):
            return self.__get_value_from_store(self.value)
        # the value is not a link, let's directly convert it to the right type
        # return self.value
        return config.TYPE_TO_PYTHON_TYPE_MAP[self.type]["type"](config.TYPE_TO_PYTHON_TYPE_MAP[self.type]["converter"](self.value))
    
    def set(self, value):
        """sets the data to the underlying port

        Arguments:
            value {any type} -- must be convertible to a string, or an exception will be thrown.
        """
        log.info("Setting data item with value %s", value)        
        # try to guess the type and check the type set fits this (there can be more than one possibility, e.g. string)
        possible_types = [key for key,key_type in config.TYPE_TO_PYTHON_TYPE_MAP.items() if isinstance(value, key_type["type"])]
        log.debug("possible types are for value %s are %s", value, possible_types)
        if not self.type in possible_types:
            if not str(self.type).startswith(config.FILE_TYPE_PREFIX) or not (isinstance(value, Path) or isinstance(value, str)):
                raise exceptions.InvalidItemTypeError(self.type, value)

        # upload to S3 if file
        if str(self.type).startswith(config.FILE_TYPE_PREFIX):
            file_path = Path(value)
            if not file_path.exists() or not file_path.is_file():
                raise exceptions.InvalidItemTypeError(self.type, value)
            pipeline_id = os.environ.get('SIMCORE_PIPELINE_ID', default="undefined")
            node_uuid = os.environ.get('SIMCORE_NODE_UUID', default="undefined")
            log.debug("file path %s will be uploaded to s3", value)
            s3_object = Path(pipeline_id, node_uuid, file_path.name).as_posix()
            filemanager.upload_file_to_s3(store="s3-z43", s3_object=s3_object, file_path=file_path)
            log.debug("file path %s uploaded to s3 in %s", value, s3_object)
            value = data_items_utils.encode_store("s3-z43", s3_object)

        # update the DB
        # let's create a new data if necessary
        new_data = DataItem(key=self.key, value=value)
        if self.new_data_cb:
            log.debug("calling new data callback to update database")
            self.new_data_cb(new_data) #pylint: disable=not-callable
            log.debug("database updated")
    
    def __get_value_from_link(self, value):    # pylint: disable=R1710
        log.debug("Getting value %s", value)
        node_uuid, port_key = data_items_utils.decode_link(value)
        if not self.get_node_from_uuid_cb:
            raise exceptions.NodeportsException("callback to get other node information is not set")
        # create a node ports for the other node
        other_nodeports = self.get_node_from_uuid_cb(node_uuid) #pylint: disable=not-callable
        # get the port value through that guy
        log.debug("Received node from DB %s, now returning value", other_nodeports)
        return other_nodeports.get(port_key)

    def __get_value_from_store(self, value):
        log.debug("Getting value from storage %s", value)
        store, s3_path = data_items_utils.decode_store(value)
        log.debug("Fetch file from S3 %s", self.value)
        file_name = Path(s3_path).name
        # if a file alias is present use it
        if self._schema.fileToKeyMap:
            file_name = next(iter(self._schema.fileToKeyMap))

        return filemanager.download_file_from_S3(store=store,            
                                                s3_object_name=s3_path,
                                                node_key=self.key,
                                                file_name=file_name)
        