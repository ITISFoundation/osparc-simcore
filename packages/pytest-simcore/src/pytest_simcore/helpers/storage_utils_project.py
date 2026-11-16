import datetime
import uuid as uuidlib
from copy import deepcopy
from typing import Any, Final

from models_library.projects_nodes_io import NodeIDStr

_PROJECT_DATETIME_COLUMNS: Final = frozenset({"creation_date", "last_change_date"})


def parse_project_dates(project: dict[str, Any]) -> dict[str, Any]:
    """Returns `project` with the `projects` table date columns parsed to datetimes.

    Service results render aware datetimes with a `Z` suffix and `jsonable_encoder`
    renders them with `+00:00`; parsing both sides of a comparison to datetimes
    compares the instants instead of their string renderings.
    """
    parsed = {**project}
    for column in _PROJECT_DATETIME_COLUMNS & project.keys():
        value = parsed[column]
        if isinstance(value, str):
            parsed[column] = datetime.datetime.fromisoformat(value)
    return parsed


def clone_project_data(
    project: dict,
) -> tuple[dict[str, Any], dict[NodeIDStr, NodeIDStr]]:
    project_copy = deepcopy(project)

    # Update project id
    # NOTE: this can be re-assigned by dbapi if not unique
    project_copy_uuid = uuidlib.uuid4()  # random project id
    project_copy["uuid"] = str(project_copy_uuid)
    project_copy.pop("id", None)
    project_copy["name"] = f"{project['name']}-copy"

    # Workbench nodes shall be unique within the project context
    def _create_new_node_uuid(old_uuid: NodeIDStr) -> NodeIDStr:
        return str(uuidlib.uuid5(project_copy_uuid, old_uuid))

    nodes_map = {}
    for node_uuid in project.get("workbench", {}):
        nodes_map[node_uuid] = _create_new_node_uuid(node_uuid)

    def _replace_uuids(node):
        if isinstance(node, str):
            node = nodes_map.get(node, node)
        elif isinstance(node, list):
            node = [_replace_uuids(item) for item in node]
        elif isinstance(node, dict):
            _frozen_items = tuple(node.items())
            for key, value in _frozen_items:
                mapped_key = nodes_map.get(key, key)
                if mapped_key != key:
                    node[mapped_key] = node.pop(key)
                node[mapped_key] = _replace_uuids(value)
        return node

    project_copy["workbench"] = _replace_uuids(project_copy.get("workbench", {}))
    return project_copy, nodes_map
