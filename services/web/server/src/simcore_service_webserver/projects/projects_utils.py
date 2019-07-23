import logging
import re
import uuid as uuidlib
from copy import deepcopy
from typing import Dict, Tuple

from servicelib.decorators import safe_return

log = logging.getLogger(__name__)
variable_pattern = re.compile(r"^{{\W*(\w+)\W*}}$")

def clone_project_document(project: Dict) -> Tuple[Dict, Dict]:
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
    return project_copy, nodes_map


@safe_return(if_fails_return=False, logger=log)
def substitute_parameterized_inputs(parameterized_project: Dict, parameters: Dict) -> Dict:
    """ Substitutes parameterized r/w inputs

        NOTE: project is is changed
    """
    project = deepcopy(parameterized_project)

    # TODO: optimize value normalization
    def _num(s):
        try:
            return int(s)
        except ValueError:
            return float(s)

    def _normalize_value(s):
        try:
            return _num(s)
        except ValueError:
            return s

    for node in project['workbench'].values():
        inputs = node.get('inputs', {})
        access = node.get('inputAccess', {})
        new_inputs = {}
        for name, value in inputs.items():
            if isinstance(value, str) and access.get(name, "ReadAndWrite") == "ReadAndWrite":
                # TODO: use jinja2 to interpolate expressions?
                m = variable_pattern.match(value)
                if m:
                    value = m.group(1)
                    if value in parameters:
                        new_inputs[name] = _normalize_value(parameters[value])
                    else:
                        log.warning("Could not resolve parameter %s. No value provided in %s", value, parameters)
        inputs.update(new_inputs)

    return project


def has_same_graph_topology(current_workbench: Dict, new_workbench: Dict) -> bool:
    try:
        for node_id, node in current_workbench.items():
            # same nodes
            assert node_id in new_workbench
            assert all(node.get(k) == new_workbench[node_id].get(k)
                for k in ['key', 'version']
            )
            # same connectivity (edges)
            assert set(node.get('inputNodes')) == set(new_workbench[node_id].get('inputNodes'))
    except (AssertionError, TypeError, AttributeError):
        return False
    return True
