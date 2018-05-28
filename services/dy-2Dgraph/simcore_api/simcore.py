"""
This class allow the client to access the inputs and outputs assigned to the node.

Example:
    $ import Simcore
    $ Simcore.input1.type

"""

import json
from datetime import datetime
import dateutil.parser
from simcore_api import config
import collections
from collections.abc import MutableSequence

DATA_ITEM_KEYS = ["key", "label", "description", "type", "value", "timestamp"]
DataItem = collections.namedtuple("DataItem", DATA_ITEM_KEYS)

class DataItemsList(MutableSequence):
    def __init__(self, data=list()):
        self.lst = data
    
    def __setitem__(self, index, value):
        self.lst[index] = value

    def __getitem__(self, index):
        return self.lst[index]

    def __len__(self):
        return len(self.lst)

    def __delitem__(self, index):
        del self.lst[index]

    def insert(self, index, value):
        self.lst.insert(index, value)

class Simcore(object):
    def __init__(self, version="0.1", inputs=DataItemsList(), outputs=DataItemsList()):
        self._version = version
        self.__inputs = inputs
        self._outputs = outputs
        self._path = r""
        self._autoupdate = False
        
    @property
    def _inputs(self):
        if self._autoupdate == True:            
            self.update_from_json_file(self._path)
        return self.__inputs
    @_inputs.setter
    def _inputs(self, inputs):
        self.__inputs = inputs
        
    def update_from_json_file(self, path):
        with open(path) as json_config:
            updated_simcore = json.load(json_config, object_hook=SimcoreDecoder)
        self.__inputs = updated_simcore.__inputs
        self._outputs = updated_simcore._outputs
        
    
    @classmethod
    def create_from_json_file(cls, path):
        with open(path) as json_config:
            simcore = json.load(json_config, object_hook=SimcoreDecoder)
        simcore._path = path
        simcore._autoupdate = True
        return simcore
        

class SimcoreEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Simcore):
            return {
                "version":obj._version,
                "inputs":obj._inputs, 
                "outputs":obj._outputs
            }
        elif isinstance(obj, DataItemsList):
            items = [data_item._asdict() for data_item in obj]
            return items
        
        return json.JSONEncoder.default(self, obj)
    
def SimcoreDecoder(dct):
    if "version" in dct and dct["version"] == "0.1" and "inputs" in dct and "outputs" in dct:
        return Simcore(dct["version"], DataItemsList(dct["inputs"]), DataItemsList(dct["outputs"]))
    else:
        for key in DATA_ITEM_KEYS:
            if key not in dct:
                return dct
        return DataItem(**dct)
