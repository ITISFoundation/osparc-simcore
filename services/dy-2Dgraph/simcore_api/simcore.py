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
DataItem = collections.namedtuple("DataItem", DATA_ITEM_KEYS)


class DataItemsList(MutableSequence): # pylint: disable=too-many-ancestors
    """This class contains a list of Data Items."""

    def __init__(self, data=None):
        _LOGGER.debug("Creating DataItemsList with %s", data)
        if data is None:
            data = []
        self.lst = data
    
    def __setitem__(self, index, value):
        _LOGGER.debug("Setting item %s with %s", index, value)
        self.lst[index] = value

    def __getitem__(self, index):
        _LOGGER.debug("Getting item %s", index)
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

#pylint: disable=C0111
class Simcore(object):
    """This class allow the client to access the inputs and outputs assigned to the node."""
    _version = "0.1"
    def __init__(self, version, inputs=None, outputs=None):
        _LOGGER.debug("Initialising Simcore object with version %s, inputs %s and outputs %s", version, inputs, outputs)
        if self._version != version:
            raise simcore_api.exceptions.WrongProtocolVersionError(self._version, version)
        
        if inputs is None:
            inputs = DataItemsList()
        self.__inputs = inputs
        if outputs is None:
            outputs = DataItemsList()
        self.__outputs = outputs
        self.__json_config = None
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
        _LOGGER.debug("Setting inputs")
        self.__inputs = value
        
    @property
    def outputs(self):
        _LOGGER.debug("Getting outputs with autoupdate: %s", self.autoupdate)
        if self.autoupdate:
            self.update_from_json()
        return self.__outputs

    @outputs.setter
    def outputs(self, value):
        _LOGGER.debug("Setting outputs")
        self.__outputs = value

    @property
    def json_config(self):
        _LOGGER.debug("Getting json configuration")
        return self.__json_config

    @json_config.setter
    def json_config(self, value):
        _LOGGER.debug("Setting json configuration")
        self.__json_config = value

    def update_from_json(self):
        _LOGGER.debug("Updating json configuration")
        updated_simcore = json.loads(self.__json_config(), object_hook=simcore_decoder)
        self.__inputs = updated_simcore.inputs
        self.outputs = updated_simcore.outputs
        _LOGGER.debug("Updated json configuration")

    @classmethod
    def create_from_json(cls, json_config):
        _LOGGER.debug("Creating Simcore object with json configuration: %s", json_config)
        simcore = json.loads(json_config(), object_hook=simcore_decoder)
        simcore.json_config = json_config
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
