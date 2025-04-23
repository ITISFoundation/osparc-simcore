import hashlib
import json
import logging
from collections.abc import Callable, Coroutine
from copy import deepcopy
from typing import Any

from pydantic import BaseModel, TypeAdapter

from ..projects import Project
from ..projects_nodes_io import NodeID, PortLink, UUIDStr

_logger = logging.getLogger(__name__)


def project_node_io_payload_cb(
    project: Project,
) -> Callable[[NodeID], Coroutine[Any, Any, dict[str, Any]]]:
    """callback fct to use together with compute_node_hash when a Project as input"""

    async def node_io_payload_cb(node_id: NodeID) -> dict[str, Any]:
        node_io_payload: dict[str, Any] = {"inputs": None, "outputs": None}
        node = project.workbench.get(TypeAdapter(UUIDStr).validate_python(node_id))
        if node:
            node_io_payload = {"inputs": node.inputs, "outputs": node.outputs}

        return node_io_payload

    return node_io_payload_cb


async def compute_node_hash(
    node_id: NodeID,
    get_node_io_payload_cb: Callable[[NodeID], Coroutine[Any, Any, dict[str, Any]]],
) -> str:
    # resolve the port links if any and get only the payload
    node_payload = deepcopy(await get_node_io_payload_cb(node_id))
    assert all(k in node_payload for k in ["inputs", "outputs"])  # nosec

    resolved_payload: dict[str, Any] = {}

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
                payload = payload.model_dump(by_alias=True, exclude_unset=True)

            # remove the payload if it is null and it was resolved
            if payload is not None:
                resolved_payload[port_type][port_key] = payload

    # now create the hash
    # WARNING: Here we cannot change to json_serialization.json_dumps because if would create a different dump string and therefore a different hash
    # NOTE that these hashes might have been already stored elsewhere
    block_string = json.dumps(resolved_payload, sort_keys=True).encode("utf-8")
    raw_hash = hashlib.sha256(block_string)
    return raw_hash.hexdigest()
