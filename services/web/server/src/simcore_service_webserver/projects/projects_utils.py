import uuid as uuidlib
from copy import deepcopy
from typing import Dict

def clone_project_data(project: Dict) -> Dict:
    project_copy = deepcopy(project)

    # Update project id
    # NOTE: this can be re-assigned by dbapi if not unique
    project_copy_uuid = uuidlib.uuid1() # random project id
    project_copy['uuid'] = str(project_copy_uuid)

    # Workbench nodes shall be unique within the project context
    def _create_new_node_uuid(old_uuid):
        return str( uuidlib.uuid5(project_copy_uuid, str(old_uuid)) )

    nodes_map = {}
    for node_uuid in project.get('workbench', {}).keys():
        nodes_map[node_uuid] = _create_new_node_uuid(node_uuid)

    def _replace_uuids(node):
        if isinstance(node, str):
            node = nodes_map.get(node, node)
        elif isinstance(node, list):
            node = [_replace_uuids(item) for item in node]
        elif isinstance(node, dict):
            _frozen_items = tuple(node.items())
            for key, value in _frozen_items:
                if key in nodes_map:
                    new_key = nodes_map[key]
                    node[new_key] = node.pop(key)
                    key = new_key
                node[key] = _replace_uuids(value)
        return node

    project_copy['workbench'] = _replace_uuids(project_copy.get('workbench', {}))
    return project_copy
