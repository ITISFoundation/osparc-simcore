"""this module allows to get the data to import from the connected previous nodes and to set the
    data going to following nodes.
"""
import collections
from collections.abc import MutableSequence
import json
import logging

import simcore_api.exceptions

_LOGGER = logging.getLogger(__name__)
DATA_ITEM_KEYS = ["key", "label", "description", "type", "value", "timestamp"]
_DataItem = collections.namedtuple("_DataItem", DATA_ITEM_KEYS)
_TYPE_TO_PYTHON_TYPE_MAP = {"int":int, "float":float, "file-url":str, "bool":bool, "string":str}

class DataItem(_DataItem):
    """This class encapsulate a Data Item and provide accessors functions"""
    def __new__(cls, **kwargs):        
        self = super(DataItem, cls).__new__(cls, **kwargs)
        self.new_data_notifier = None
        return self

    def get(self): #pylint: disable=C0111
        if self.type not in _TYPE_TO_PYTHON_TYPE_MAP:
            raise simcore_api.exceptions.InvalidProtocolError(self.type)
        if self.value == "null":
            return None
        return _TYPE_TO_PYTHON_TYPE_MAP[self.type](self.value)

    def set(self, value): #pylint: disable=C0111
        # let's create a new data
        data_dct = self._asdict()
        new_value = str(value)
        if new_value != data_dct["value"]:
            data_dct["value"] = str(value)
            new_data = DataItem(**data_dct)
            if self.new_data_notifier:
                self.new_data_notifier(new_data) #pylint: disable=not-callable
            #notify_new_data(newData)

class DataItemsList(MutableSequence): # pylint: disable=too-many-ancestors
    """This class contains a list of Data Items."""

    def __init__(self, data=None, read_only=False):
        _LOGGER.debug("Creating DataItemsList with %s", data)
        if data is None:
            data = []
        self.lst = data
        self.read_only = read_only
        self.__change_notifier = None
    
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
            raise simcore_api.exceptions.ReadOnlyError(self)        
        if isinstance(index, str):
            # it might be a key            
            index = self.__find_index_from_key(index)
        self.lst[index] = value
        if self.change_notifier and callable(self.change_notifier):
            self.change_notifier() #pylint: disable=not-callable

    def __getitem__(self, index):
        _LOGGER.debug("Getting item %s", index)
        if isinstance(index, str):
            # it might be a key
            index = self.__find_index_from_key(index)
        if index < len(self.lst):
            return self.lst[index]
        raise simcore_api.exceptions.UnboundPortError(index)

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
            raise simcore_api.exceptions.InvalidKeyError(item_key)
        if len(indices) > 1:
            raise simcore_api.exceptions.InvalidProtocolError(indices)
        return indices[0]

    def __assign_change_notifier_to_data(self):
        for data in self.lst:
            data.new_data_notifier = self.__item_value_updated_cb

    def __item_value_updated_cb(self, new_data_item):
        # a new item shall replace the current one
        item_index = self.__find_index_from_key(new_data_item.key)
        self.lst[item_index] = new_data_item
        if self.change_notifier and callable(self.change_notifier):
            self.change_notifier() #pylint: disable=not-callable

#pylint: disable=C0111
class Simcore(object):
    """This class allow the client to access the inputs and outputs assigned to the node."""
    _version = "0.1"
    def __init__(self, version, inputs=None, outputs=None):
        _LOGGER.debug("Initialising Simcore object with version %s, inputs %s and outputs %s", version, inputs, outputs)
        if self._version != version:
            raise simcore_api.exceptions.WrongProtocolVersionError(self._version, version)
        
        # inputs are per definition read-only
        if inputs is None:
            inputs = DataItemsList()
        self.__inputs = inputs
        self.__inputs.read_only = True

        # outputs are currently read-only as we do not allow dynamic change of
        # number of outputs or changing their type or so for now.
        if outputs is None:
            outputs = DataItemsList()
        self.__outputs = outputs
        self.__outputs.read_only = True
        self.__outputs.change_notifier = self.save_to_json

        self.__json_reader = None
        self.__json_writer = None
        self.autoupdate = False
        _LOGGER.debug("Initialised Simcore object with version %s, inputs %s and outputs %s", version, inputs, outputs)
        
    @property
    def inputs(self):
        _LOGGER.debug("Getting inputs with autoupdate: %s", self.autoupdate)
        if self.autoupdate:                        
            self.update_from_json()
        return self.__inputs

    @inputs.setter
    def inputs(self, value):
        # this is forbidden        
        _LOGGER.debug("Setting inputs with %s", value)
        raise simcore_api.exceptions.ReadOnlyError(self.__inputs)
        #self.__inputs = value
        
    @property
    def outputs(self):
        _LOGGER.debug("Getting outputs with autoupdate: %s", self.autoupdate)
        if self.autoupdate:
            self.update_from_json()
        return self.__outputs

    @outputs.setter
    def outputs(self, value):
        # this is forbidden        
        _LOGGER.debug("Setting outputs with %s", value)
        raise simcore_api.exceptions.ReadOnlyError(self.__outputs)
        #self.__outputs = value

    @property
    def json_reader(self):
        _LOGGER.debug("Getting json configuration")
        return self.__json_reader

    @json_reader.setter
    def json_reader(self, value):
        _LOGGER.debug("Setting json configuration with %s", value)
        self.__json_reader = value
    
    @property
    def json_writer(self):
        _LOGGER.debug("Getting json writer")
        return self.__json_writer

    @json_writer.setter
    def json_writer(self, value):
        _LOGGER.debug("Setting json writer with %s", value)
        self.__json_writer = value

    def update_from_json(self):
        _LOGGER.debug("Updating json configuration")
        change_notifier = self.__outputs.change_notifier
        updated_simcore = json.loads(self.__json_reader(), object_hook=simcore_decoder)
        self.__inputs = updated_simcore.inputs
        self.__outputs = updated_simcore.outputs
        self.__outputs.change_notifier = change_notifier
        _LOGGER.debug("Updated json configuration")
    
    def save_to_json(self):
        _LOGGER.info("Saving Simcore object to json")
        auto_update_state = self.autoupdate
        try:
            # dumping triggers a load of unwanted auto-updates
            # which do not make sense for saving purpose.
            self.autoupdate = False
            simcore_json = json.dumps(self, cls=_SimcoreEncoder)
        finally:
            self.autoupdate = auto_update_state
        
        if callable(self.json_writer):
            self.json_writer(simcore_json) #pylint: disable=E1102
        _LOGGER.debug("Saved Simcore object to json: %s", simcore_json)

    @classmethod
    def create_from_json(cls, json_reader, json_writer):
        _LOGGER.debug("Creating Simcore object with json reader: %s, json writer: %s", json_reader, json_writer)
        simcore = json.loads(json_reader(), object_hook=simcore_decoder)
        simcore.json_reader = json_reader
        simcore.json_writer = json_writer
        simcore.autoupdate = True
        _LOGGER.debug("Created Simcore object")
        return simcore

class _SimcoreEncoder(json.JSONEncoder):
    # SAN: looks like pylint is having an issue here
    def default(self, o): # pylint: disable=E0202
        _LOGGER.debug("Encoding object: %s", o)
        if isinstance(o, Simcore):
            _LOGGER.debug("Encoding Simcore object")
            return {
                "version": o._version, # pylint: disable=W0212
                "inputs": o.inputs, # pylint: disable=W0212
                "outputs": o.outputs # pylint: disable=W0212
            }
        elif isinstance(o, DataItemsList):
            _LOGGER.debug("Encoding DataItemsList object")
            items = [data_item._asdict() for data_item in o]
            return items
        _LOGGER.debug("Encoding object using defaults")
        return json.JSONEncoder.default(self, o)
    
def simcore_decoder(dct):
    if "version" in dct and "inputs" in dct and "outputs" in dct:
        _LOGGER.debug("Decoding Simcore json: %s", dct)
        return Simcore(dct["version"], DataItemsList(dct["inputs"]), DataItemsList(dct["outputs"]))
    for key in DATA_ITEM_KEYS:
        if key not in dct:
            raise simcore_api.exceptions.InvalidProtocolError(dct)
    _LOGGER.debug("Decoding Data time json: %s", dct)
    return DataItem(**dct)
