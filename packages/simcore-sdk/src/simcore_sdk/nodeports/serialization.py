"""this module is responsible for JSON encoding/decoding of nodeports objects."""
import json
import logging

from simcore_sdk.nodeports import nodeports #pylint: disable=cyclic-import
from simcore_sdk.nodeports._itemslist import DataItemsList
from simcore_sdk.nodeports._item import DataItem
from simcore_sdk.nodeports import exceptions
from simcore_sdk.nodeports import config
from simcore_sdk.models.pipeline_models import ComputationalTask as NodeModel

_LOGGER = logging.getLogger(__name__)

def create_from_json(json_reader_cb, json_writer_cb=None, auto_update=False):
    """creates a Nodeports object provided a json configuration in form of a callback function.
    
    Arguments:
        json_reader_cb {callback function} -- upon call shall return the json configuration to create the Nodeports object
        json_writer_cb {callback function} -- upcon call shall take a Nodeports json configuration to write
    
    Raises:
        exceptions.NodeportsException -- raised when json_reader_cb is empty
    
    Returns:
        Nodeports -- the Nodeports object
    """

    _LOGGER.debug("Creating Nodeports object with json reader: %s, json writer: %s", json_reader_cb, json_writer_cb)
    if json_reader_cb is None:
        raise exceptions.NodeportsException("json reader callback is empty, this is not allowed")
    nodeports_obj = json.loads(json_reader_cb(), object_hook=nodeports_decoder)
    nodeports_obj.json_reader = json_reader_cb
    nodeports_obj.json_writer = json_writer_cb
    nodeports_obj.autoupdate = auto_update
    _LOGGER.debug("Created Nodeports object")
    return nodeports_obj

def save_to_json(obj):
    """encodes a Nodeports object to json and calls a linked writer if available.
    
    Arguments:
        obj {Nodeports} -- the object to encode
    """

    auto_update_state = obj.autoupdate
    try:
        # dumping triggers a load of unwanted auto-updates
        # which do not make sense for saving purpose.
        obj.autoupdate = False
        nodeports_json = json.dumps(obj, cls=_NodeportsEncoder)
    finally:
        obj.autoupdate = auto_update_state
    
    if callable(obj.json_writer):
        obj.json_writer(nodeports_json) #pylint: disable=E1102
    _LOGGER.info("Saved Nodeports object to json: %s", nodeports_json)

class _NodeportsEncoder(json.JSONEncoder):
    # SAN: looks like pylint is having an issue here
    def default(self, o): # pylint: disable=E0202
        _LOGGER.debug("Encoding object: %s", o)
        if isinstance(o, nodeports.Nodeports):
            _LOGGER.debug("Encoding Nodeports object")
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
    
def nodeports_decoder(dct):
    """JSON decoder for Nodeports objects.
    
    Arguments:
        dct {dictionary} -- represents json configuration of a Nodeports object
    
    Raises:
        exceptions.InvalidProtocolError -- if the protocol is not recognized
    
    Returns:
        Nodeports,DataItemsList,DataItem -- objects necessary for a complete JSON decoding
    """

    if "version" in dct and "inputs" in dct and "outputs" in dct:
        _LOGGER.debug("Decoding Nodeports json: %s", dct)
        return nodeports.Nodeports(dct["version"], DataItemsList(dct["inputs"]), DataItemsList(dct["outputs"]))
    for key in config.DATA_ITEM_KEYS:
        if key not in dct:
            raise exceptions.InvalidProtocolError(dct, "key \"%s\" is missing" % (str(key)))
    _LOGGER.debug("Decoding Data items json: %s", dct)
    return DataItem(**dct)

def save_node_to_json(node):
    node_json_config = json.dumps(node, cls=_NodeModelEncoder)
    return node_json_config

def create_node_from_json(json_config):
    node = json.loads(json_config, object_hook=nodemodel_decoder)
    return node

class _NodeModelEncoder(json.JSONEncoder):
    def default(self, o): # pylint: disable=E0202
        _LOGGER.debug("Encoding object: %s", o)
        if isinstance(o, NodeModel):
            _LOGGER.debug("Encoding Node object")
            return {"version": "0.1", 
                    "inputs": o.input, 
                    "outputs": o.output
                    }
            # return {"version": o.tag, 
            #         "inputs": o.inputs, 
            #         "outputs": o.outputs
            #         }
        _LOGGER.debug("Encoding object using defaults")
        return json.JSONEncoder.default(self, o)

def nodemodel_decoder(dct):
    if "version" in dct and "inputs" in dct and "outputs" in dct:
        _LOGGER.debug("Decoding Nodeports json: %s", dct)
        return NodeModel(input=dct["inputs"], output=dct["outputs"])
        #return NodeModel(tag=dct["version"], inputs=dct["inputs"], outputs=dct["outputs"])
    # for key in config.DATA_ITEM_KEYS:
    #     if key not in dct:
    #         raise exceptions.InvalidProtocolError(dct)
    # _LOGGER.debug("Decoding Data items json: %s", dct)
    return dct