import hashlib
import json
import logging
from copy import deepcopy
from pprint import pformat
from typing import Any, Callable, Coroutine, Dict

from models_library.projects_nodes import NodeID
from models_library.projects_nodes_io import PortLink
from pydantic import BaseModel

logger = logging.getLogger(__name__)


async def compute_node_hash(
    node_id: NodeID,
    get_node_io_payload_cb: Callable[[NodeID], Coroutine[Any, Any, Dict[str, Any]]],
) -> str:
    # resolve the port links if any and get only the payload
    node_payload = deepcopy(await get_node_io_payload_cb(node_id))
    assert all(k in node_payload for k in ["inputs", "outputs"])  # nosec

    resolved_payload = {}

    for port_type in ["inputs", "outputs"]:
        port_type_payloads = node_payload.get(port_type)
        # the payload might be None
        resolved_payload[port_type] = None
        if port_type_payloads is None:
            continue

        resolved_payload[port_type] = {}
        # we have a payload, let's resolve and make is jsoneable
        for port_key, port_value in port_type_payloads.items():
            payload = port_value
            if isinstance(port_value, PortLink):
                # in case of a port link we do resolve the entry so we have the real value for the hashing
                previous_node = await get_node_io_payload_cb(port_value.node_uuid)
                previous_node_outputs = previous_node.get("outputs", {})
                payload = previous_node_outputs.get(port_value.output)

            # ensure we do not get pydantic types for hashing here, only jsoneable stuff
            if isinstance(payload, BaseModel):
                payload = payload.dict(by_alias=True, exclude_unset=True)

            # remove the payload if it is null and it was resolved
            if payload is not None:
                resolved_payload[port_type][port_key] = payload

    # now create the hash
    logger.debug("io_payload generated is %s", pformat(resolved_payload))
    block_string = json.dumps(resolved_payload, sort_keys=True).encode("utf-8")
    logger.debug("block string generated is %s", block_string)
    raw_hash = hashlib.sha256(block_string)
    logger.debug("generated hash %s", raw_hash)
    return raw_hash.hexdigest()
