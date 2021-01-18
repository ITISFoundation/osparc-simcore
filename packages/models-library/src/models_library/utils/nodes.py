import hashlib
import json
import logging
from pprint import pformat
from typing import Any, Callable, Dict

from models_library.projects_nodes import NodeID
from models_library.projects_nodes_io import PortLink
from pydantic import BaseModel

logger = logging.getLogger(__name__)


def compute_node_hash(
    node_io: Dict[str, Any], other_node_io_cb: Callable[[NodeID], Dict[str, Any]]
) -> str:
    # resolve the port links if any and get only the payload
    io_payload = {}
    for port_type in ["inputs", "outputs"]:
        io_payload[port_type] = {}
        for port_key, port_value in node_io[port_type].items():
            payload = port_value
            if isinstance(port_value, PortLink):
                # in case of a port link we do resolve the entry so we have the real value for the hashing
                previous_node = other_node_io_cb(port_value.node_uuid)
                previous_node_outputs = previous_node.get("outputs", {})
                payload = previous_node_outputs.get(port_value.output)

            # ensure we do not get pydantic types for hashing here, only jsoneable stuff
            if isinstance(payload, BaseModel):
                payload = payload.dict(by_alias=True, exclude_unset=True)

            # if there is no payload do not add it
            if payload is not None:
                io_payload[port_type][port_key] = payload

    # now create the hash
    logger.debug("io_payload generated is %s", pformat(io_payload))
    block_string = json.dumps(io_payload, sort_keys=True).encode("utf-8")
    logger.debug("block string generated is %s", block_string)
    raw_hash = hashlib.sha256(block_string)
    logger.debug("generated hash %s", raw_hash)
    return raw_hash.hexdigest()
