""" This module is responsible for JSON encoding/decoding of nodeports objects

"""
import json
import logging
from typing import Dict

# FIXME: : nodeports.Nodeports produces recursive import
from . import config, exceptions, nodeports
from ._data_item import DataItem
from ._data_items_list import DataItemsList
from ._schema_item import SchemaItem
from ._schema_items_list import SchemaItemsList
from .dbmanager import DBManager

log = logging.getLogger(__name__)


async def create_from_json(
    db_mgr: DBManager, auto_read: bool = False, auto_write: bool = False
):
    """ creates a Nodeports object provided a json configuration in form of a callback function

    :param db_mgr: interface object to connect to nodeports description
    :param auto_read: the nodeports object shall automatically update itself when set to True, defaults to False
    :param auto_read: bool, optional
    :param auto_write: the nodeports object shall automatically write the new outputs when set to True, defaults to False
    :param auto_write: bool, optional
    :raises exceptions.NodeportsException: when io object is empty
    :return: the Nodeports object
    """

    log.debug(
        "Creating Nodeports object with io object: %s, auto read %s and auto write %s",
        db_mgr,
        auto_read,
        auto_write,
    )
    if not db_mgr:
        raise exceptions.NodeportsException("io object empty, this is not allowed")
    nodeports_dict = json.loads(
        await db_mgr.get_ports_configuration_from_node_uuid(config.NODE_UUID)
    )
    nodeports_obj = __decodeNodePorts(nodeports_dict)
    nodeports_obj.db_mgr = db_mgr
    nodeports_obj.autoread = auto_read
    nodeports_obj.autowrite = auto_write
    log.debug("Created Nodeports object")
    return nodeports_obj


async def create_nodeports_from_uuid(db_mgr: DBManager, node_uuid: str):
    log.debug("Creating Nodeports object from node uuid: %s", node_uuid)
    if not db_mgr:
        raise exceptions.NodeportsException(
            "Invalid call to create nodeports from uuid"
        )
    nodeports_dict = json.loads(
        await db_mgr.get_ports_configuration_from_node_uuid(node_uuid)
    )
    nodeports_obj = __decodeNodePorts(nodeports_dict)
    log.debug("Created Nodeports object")
    return nodeports_obj


async def save_to_json(nodeports_obj) -> None:
    """ Encodes a Nodeports object to json and calls a linked writer if available.

    :param nodeports_obj:  the object to encode
    :type nodeports_obj: Nodeports
    """
    auto_update_state = nodeports_obj.autoread
    try:
        # dumping triggers a load of unwanted auto-updates
        # which do not make sense for saving purpose.
        nodeports_obj.autoread = False
        nodeports_json = json.dumps(nodeports_obj, cls=_NodeportsEncoder)
    finally:
        nodeports_obj.autoread = auto_update_state

    if nodeports_obj.autowrite:
        await nodeports_obj.db_mgr.write_ports_configuration(
            nodeports_json, config.NODE_UUID
        )
    log.debug("Saved Nodeports object to json: %s", nodeports_json)


class _NodeportsEncoder(json.JSONEncoder):
    # SAN: looks like pylint is having an issue here
    def default(self, o):  # pylint: disable=E0202
        log.debug("Encoding object: %s", o)
        if isinstance(o, nodeports.Nodeports):
            log.debug("Encoding Nodeports object")
            return {
                # pylint: disable=W0212
                "version": o._version,
                "schema": {"inputs": o._input_schemas, "outputs": o._output_schemas,},
                "inputs": o._inputs_payloads,
                "outputs": o._outputs_payloads,
            }
        if isinstance(o, SchemaItemsList):
            log.debug("Encoding SchemaItemsList object")
            items = {
                key: {
                    item_key: item_value
                    for item_key, item_value in item._asdict().items()
                    if item_key != "key"
                }
                for key, item in o.items()
            }
            return items
        if isinstance(o, DataItemsList):
            log.debug("Encoding DataItemsList object")
            items = {key: item.value for key, item in o.items()}
            return items
        log.debug("Encoding object using defaults")
        return json.JSONEncoder.default(self, o)


def __decodeNodePorts(dct: Dict):
    if not all(k in dct for k in config.NODE_KEYS.keys()):
        raise exceptions.InvalidProtocolError(dct)
    # decode schema
    schema = dct["schema"]
    if not all(k in schema for k in ("inputs", "outputs")):
        raise exceptions.InvalidProtocolError(dct, "invalid schemas")
    decoded_input_schema = SchemaItemsList(
        {key: SchemaItem(key=key, **value) for key, value in schema["inputs"].items()}
    )
    decoded_output_schema = SchemaItemsList(
        {key: SchemaItem(key=key, **value) for key, value in schema["outputs"].items()}
    )
    # decode payload
    decoded_input_payload = DataItemsList(
        {key: DataItem(key=key, value=value) for key, value in dct["inputs"].items()}
    )
    decoded_output_payload = DataItemsList(
        {key: DataItem(key=key, value=value) for key, value in dct["outputs"].items()}
    )

    return nodeports.Nodeports(
        dct["version"],
        SchemaItemsList(decoded_input_schema),
        SchemaItemsList(decoded_output_schema),
        DataItemsList(decoded_input_payload),
        DataItemsList(decoded_output_payload),
    )
