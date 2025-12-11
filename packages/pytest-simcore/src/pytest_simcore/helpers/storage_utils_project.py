import uuid as uuidlib
from copy import deepcopy
from typing import Any

from models_library.projects_nodes_io import NodeID


def clone_project_data(
    project: dict[str, Any],
    project_nodes: dict[NodeID, dict[str, Any]],
) -> tuple[dict[str, Any], dict[NodeID, dict[str, Any]], dict[NodeID, NodeID]]:
    project_copy = deepcopy(project)

    # Update project id
    # NOTE: this can be re-assigned by dbapi if not unique
    project_copy_uuid = uuidlib.uuid4()  # random project id
    project_copy["uuid"] = str(project_copy_uuid)
    project_copy.pop("id", None)
    project_copy["name"] = f"{project['name']}-copy"

    # Nodes shall be unique within the project context
    def _new_node_uuid(old: NodeID) -> NodeID:
        return uuidlib.uuid5(project_copy_uuid, f"{old}")

    nodes_map = {node_uuid: _new_node_uuid(node_uuid) for node_uuid in project_nodes}
    project_nodes_copy = {
        nodes_map[old_node_id]: {
            **deepcopy(data),
            "node_id": nodes_map[old_node_id],  # update the internal "node_id" field
        }
        for old_node_id, data in project_nodes.items()
    }

    return project_copy, project_nodes_copy, nodes_map
