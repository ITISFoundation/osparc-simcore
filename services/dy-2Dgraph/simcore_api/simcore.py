"""this module allows to get the data to import from the connected previous nodes and to set the
    data going to following nodes.
"""
import collections
from collections.abc import MutableSequence
import json

DATA_ITEM_KEYS = ["key", "label", "description", "type", "value", "timestamp"]
DataItem = collections.namedtuple("DataItem", DATA_ITEM_KEYS)


class DataItemsList(MutableSequence):
    """This class contains a list of Data Items."""

    def __init__(self, data=None):
        if data is None:
            data = []
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

#pylint: disable=C0111
class Simcore(object):
    """This class allow the client to access the inputs and outputs assigned to the node."""

    def __init__(self, version="0.1", inputs=None, outputs=None):
        self._version = version
        if inputs is None:
            inputs = DataItemsList()
        self.__inputs = inputs
        if outputs is None:
            outputs = DataItemsList()
        self.__outputs = outputs
        self.path = r""
        self.autoupdate = False
        
    @property
    def inputs(self):
        if self.autoupdate:            
            self.update_from_json_file(self.path)
        return self.__inputs

    @inputs.setter
    def inputs(self, value):
        self.__inputs = value
        
    @property
    def outputs(self):
        if self.autoupdate:
            self.update_from_json_file(self.path)
        return self.__outputs

    @outputs.setter
    def outputs(self, value):
        self.__outputs = value

    def update_from_json_file(self, path):
        with open(path) as json_config:
            updated_simcore = json.load(json_config, object_hook=simcore_decoder)
        self.__inputs = updated_simcore.inputs
        self.outputs = updated_simcore.outputs
        
    @classmethod
    def create_from_json_file(cls, path):
        with open(path) as json_config:
            simcore = json.load(json_config, object_hook=simcore_decoder)
        simcore.path = path
        simcore.autoupdate = True
        return simcore

class _SimcoreEncoder(json.JSONEncoder):
    # SAN: looks like pylint is having an issue here
    def default(self, o): # pylint: disable=E0202
        if isinstance(o, Simcore):
            return {
                "version": o._version, # pylint: disable=W0212
                "inputs": o._inputs, # pylint: disable=W0212
                "outputs": o._outputs # pylint: disable=W0212
            }
        elif isinstance(o, DataItemsList):
            items = [data_item._asdict() for data_item in o]
            return items
        
        return json.JSONEncoder.default(self, o)
    
def simcore_decoder(dct):
    if "version" in dct and dct["version"] == "0.1" and "inputs" in dct and "outputs" in dct:
        return Simcore(dct["version"], DataItemsList(dct["inputs"]), DataItemsList(dct["outputs"]))
    else:
        for key in DATA_ITEM_KEYS:
            if key not in dct:
                return dct
        return DataItem(**dct)
