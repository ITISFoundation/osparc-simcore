import uuid as uuidlib
from copy import deepcopy
from typing import Any, overload

from models_library.projects_nodes_io import NodeID, NodeIDStr


@overload
def clone_project_data(
    project: dict[str, Any],
) -> tuple[dict[str, Any], dict[NodeIDStr, NodeIDStr]]: ...


@overload
def clone_project_data(
    project: dict[str, Any],
    project_nodes: dict[NodeID, dict[str, Any]],
) -> tuple[dict[str, Any], dict[NodeID, dict[str, Any]], dict[NodeID, NodeID]]: ...


def clone_project_data(
    project: dict[str, Any],
    project_nodes: dict[NodeID, dict[str, Any]] | None = None,
) -> (
    tuple[dict[str, Any], dict[NodeIDStr, NodeIDStr]]
    | tuple[dict[str, Any], dict[NodeID, dict[str, Any]], dict[NodeID, NodeID]]
):
    project_copy = deepcopy(project)

    # Update project id
    # NOTE: this can be re-assigned by dbapi if not unique
    project_copy_uuid = uuidlib.uuid4()  # random project id
    project_copy["uuid"] = str(project_copy_uuid)
    project_copy.pop("id", None)
    project_copy["name"] = f"{project['name']}-copy"

    if project_nodes is not None:
        # New calling convention: separate project_nodes dict
        def _new_node_uuid(old: NodeID) -> NodeID:
            return uuidlib.uuid5(project_copy_uuid, f"{old}")

        nodes_map = {node_uuid: _new_node_uuid(node_uuid) for node_uuid in project_nodes}
        project_nodes_copy = {
            nodes_map[old_node_id]: {
                **deepcopy(data),
                "node_id": nodes_map[old_node_id],
            }
            for old_node_id, data in project_nodes.items()
        }

        return project_copy, project_nodes_copy, nodes_map

    # Legacy calling convention: workbench embedded in project dict
    def _create_new_node_uuid(old_uuid: NodeIDStr) -> NodeIDStr:
        return NodeIDStr(uuidlib.uuid5(project_copy_uuid, old_uuid))

    nodes_map_str: dict[NodeIDStr, NodeIDStr] = {}
    for node_uuid in project.get("workbench", {}):
        nodes_map_str[node_uuid] = _create_new_node_uuid(node_uuid)

    def _replace_uuids(node):
        if isinstance(node, str):
            node = nodes_map_str.get(node, node)
        elif isinstance(node, list):
            node = [_replace_uuids(item) for item in node]
        elif isinstance(node, dict):
            _frozen_items = tuple(node.items())
            for key, value in _frozen_items:
                if key in nodes_map_str:
                    new_key = nodes_map_str[key]
                    node[new_key] = node.pop(key)
                    key = new_key
                node[key] = _replace_uuids(value)
        return node

    project_copy["workbench"] = _replace_uuids(project_copy.get("workbench", {}))
    return project_copy, nodes_map_str
