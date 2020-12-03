import json
from typing import List

from aiopg.sa.result import RowProxy

from ..node_ports.dbmanager import DBManager
from ..node_ports.exceptions import InvalidProtocolError
from .nodeports_v2 import Nodeports

NODE_REQUIORED_KEYS: List[str] = {
    "schema",
    "inputs",
    "outputs",
}


async def create_nodeports_from_db(
    db_manager: DBManager, node_uuid: str, auto_update: bool = False
) -> Nodeports:
    """creates a nodeport object from a row from comp_tasks"""
    row: RowProxy = await db_manager.get_ports_configuration_from_node_uuid(node_uuid)
    port_cfg = json.loads(row)
    if any(k not in port_cfg for k in NODE_REQUIORED_KEYS):
        raise InvalidProtocolError(
            port_cfg, "nodeport in comp_task does not follow protocol"
        )
    # convert to our internal node ports
    _PY_INT = "__root__"
    node_ports_cfg = {"inputs": {_PY_INT: {}}, "outputs": {_PY_INT: {}}}
    for port_type in ["inputs", "outputs"]:
        # schemas first
        node_ports_cfg.update(
            {
                port_type: {_PY_INT: port_cfg["schema"][port_type]},
            }
        )
        # add the key and the payload
        for key, port_value in node_ports_cfg[port_type][_PY_INT].items():
            port_value["key"] = key
            port_value["value"] = port_cfg[port_type].get(key, None)

    ports = Nodeports(
        **node_ports_cfg,
        db_manager=db_manager,
        node_uuid=node_uuid,
        save_to_db_cb=save_nodeports_to_db,
        node_port_creator_cb=create_nodeports_from_db,
        auto_update=auto_update
    )
    return ports


async def save_nodeports_to_db(nodeports: Nodeports):
    _nodeports_cfg = nodeports.dict(
        include={"internal_inputs", "internal_outputs"},
        by_alias=True,
        exclude_unset=True,
    )

    # convert to DB
    port_cfg = {"schema": {"inputs": {}, "outputs": {}}, "inputs": {}, "outputs": {}}
    for port_type in ["inputs", "outputs"]:
        for port_key, port_values in _nodeports_cfg[port_type].items():
            # schemas
            key_schema = {
                k: v
                for k, v in _nodeports_cfg[port_type][port_key].items()
                if k not in ["key", "value"]
            }
            port_cfg["schema"][port_type][port_key] = key_schema
            # payload
            port_cfg[port_type][port_key] = port_values["value"]

    await nodeports.db_manager.write_ports_configuration(
        json.dumps(port_cfg), nodeports.node_uuid
    )
