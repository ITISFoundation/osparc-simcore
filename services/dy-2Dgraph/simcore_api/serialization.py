"""this module is responsible for JSON encoding/decoding of simcore_api objects."""
import json
import logging

from simcore_api import simcore
from simcore_api._itemslist import DataItemsList
from simcore_api._item import DataItem
from simcore_api import exceptions
from simcore_api import config

_LOGGER = logging.getLogger(__name__)

def create_from_json(json_reader_cb, json_writer_cb=None, auto_update=False):
    """creates a Simcore object provided a json configuration in form of a callback function.
    
    Arguments:
        json_reader_cb {callback function} -- upon call shall return the json configuration to create the Simcore object
        json_writer_cb {callback function} -- upcon call shall take a Simcore json configuration to write
    
    Raises:
        exceptions.SimcoreException -- raised when json_reader_cb is empty
    
    Returns:
        Simcore -- the Simcore object
    """

    _LOGGER.debug("Creating Simcore object with json reader: %s, json writer: %s", json_reader_cb, json_writer_cb)
    if json_reader_cb is None:
        raise exceptions.SimcoreException("json reader callback is empty, this is not allowed")
    simcore_obj = json.loads(json_reader_cb(), object_hook=simcore_decoder)
    simcore_obj.json_reader = json_reader_cb
    simcore_obj.json_writer = json_writer_cb
    simcore_obj.autoupdate = auto_update
    _LOGGER.debug("Created Simcore object")
    return simcore_obj

def save_to_json(obj):
    """encodes a Simcore object to json and calls a linked writer if available.
    
    Arguments:
        obj {Simcore} -- the object to encode
    """

    auto_update_state = obj.autoupdate
    try:
        # dumping triggers a load of unwanted auto-updates
        # which do not make sense for saving purpose.
        obj.autoupdate = False
        simcore_json = json.dumps(obj, cls=_SimcoreEncoder)
    finally:
        obj.autoupdate = auto_update_state
    
    if callable(obj.json_writer):
        obj.json_writer(simcore_json) #pylint: disable=E1102
    _LOGGER.info("Saved Simcore object to json: %s", simcore_json)

class _SimcoreEncoder(json.JSONEncoder):
    # SAN: looks like pylint is having an issue here
    def default(self, o): # pylint: disable=E0202
        _LOGGER.debug("Encoding object: %s", o)
        if isinstance(o, simcore.Simcore):
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
    """JSON decoder for simcore objects.
    
    Arguments:
        dct {dictionary} -- represents json configuration of a simcore object
    
    Raises:
        exceptions.InvalidProtocolError -- if the protocol is not recognized
    
    Returns:
        Simcore,DataItemsList,DataItem -- objects necessary for a complete JSON decoding
    """

    if "version" in dct and "inputs" in dct and "outputs" in dct:
        _LOGGER.debug("Decoding Simcore json: %s", dct)
        return simcore.Simcore(dct["version"], DataItemsList(dct["inputs"]), DataItemsList(dct["outputs"]))
    for key in config.DATA_ITEM_KEYS:
        if key not in dct:
            raise exceptions.InvalidProtocolError(dct)
    _LOGGER.debug("Decoding Data time json: %s", dct)
    return DataItem(**dct)
