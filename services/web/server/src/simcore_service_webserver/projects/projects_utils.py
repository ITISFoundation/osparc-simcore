import logging
import re
import uuid as uuidlib
from copy import deepcopy
from typing import Dict, Tuple

from servicelib.decorators import safe_return

log = logging.getLogger(__name__)
variable_pattern = re.compile(r"^{{\W*(\w+)\W*}}$")

def clone_project_document(project: Dict, forced_copy_project_id: str ="") -> Tuple[Dict, Dict]:
    project_copy = deepcopy(project)

    # Update project id
    # NOTE: this can be re-assigned by dbapi if not unique
    if forced_copy_project_id:
        project_copy_uuid = uuidlib.UUID(forced_copy_project_id)
    else:
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


def is_graph_equal(lhs_workbench: Dict, rhs_workbench: Dict) -> bool:
    """ Checks whether both workbench contain the same graph

        Two graphs are the same when the same topology (i.e. nodes and edges)
        and the ports at each node have same values/connections
    """
    try:
        if not set(rhs_workbench.keys()) == set(lhs_workbench.keys()):
            raise ValueError()

        for node_id, node in rhs_workbench.items():
            # same nodes
            if not all(node.get(k) == lhs_workbench[node_id].get(k) for k in ['key', 'version'] ):
                raise ValueError()

            # same connectivity (edges)
            if not set(node.get('inputNodes')) == set(lhs_workbench[node_id].get('inputNodes')):
                raise ValueError()

            # same input values
            for port_id, port in node.get("inputs", {}).items():
                if port != lhs_workbench[node_id].get("inputs", {}).get(port_id):
                    raise ValueError()

    except (ValueError, TypeError, AttributeError):
        return False
    return True
