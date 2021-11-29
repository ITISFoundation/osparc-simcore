import logging
import re
from copy import deepcopy
from typing import Any, AnyStr, Dict, List, Match, Optional, Set, Tuple, Union
from uuid import UUID, uuid1, uuid5

from servicelib.decorators import safe_return
from yarl import URL

log = logging.getLogger(__name__)
variable_pattern = re.compile(r"^{{\W*(\w+)\W*}}$")


def clone_project_document(
    project: Dict,
    *,
    forced_copy_project_id: Optional[UUID] = None,
    clean_output_data: bool = False,
) -> Tuple[Dict, Dict]:
    project_copy = deepcopy(project)

    # Update project id
    # NOTE: this can be re-assigned by dbapi if not unique
    if forced_copy_project_id:
        assert isinstance(forced_copy_project_id, UUID)  # nosec
        project_copy_uuid = forced_copy_project_id
    else:
        project_copy_uuid = uuid1()  # random project id

    assert project_copy_uuid  # nosec

    project_copy["uuid"] = str(project_copy_uuid)

    # Workbench nodes shall be unique within the project context
    def _create_new_node_uuid(old_uuid):
        return str(uuid5(project_copy_uuid, str(old_uuid)))

    nodes_map = {}
    for node_uuid in project.get("workbench", {}).keys():
        nodes_map[node_uuid] = _create_new_node_uuid(node_uuid)

    project_map = {project["uuid"]: project_copy["uuid"]}

    def _replace_uuids(node: Union[str, List, Dict]) -> Union[str, List, Dict]:
        if isinstance(node, str):
            # NOTE: for datasets we get something like project_uuid/node_uuid/file_id
            if "/" in node:
                parts = node.split("/")
                node = "/".join(_replace_uuids(part) for part in parts)
            else:
                node = project_map.get(node, nodes_map.get(node, node))
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

    project_copy["workbench"] = _replace_uuids(project_copy.get("workbench", {}))
    if "ui" in project_copy:
        project_copy["ui"]["workbench"] = _replace_uuids(
            project_copy["ui"].get("workbench", {})
        )
        project_copy["ui"]["slideshow"] = _replace_uuids(
            project_copy["ui"].get("slideshow", {})
        )
        if "mode" in project_copy["ui"]:
            project_copy["ui"]["mode"] = project_copy["ui"]["mode"]
    if clean_output_data:
        FIELDS_TO_DELETE = ("outputs", "progress", "runHash")
        for node_data in project_copy.get("workbench", {}).values():
            for field in FIELDS_TO_DELETE:
                node_data.pop(field, None)
    return project_copy, nodes_map


@safe_return(if_fails_return=False, logger=log)
def substitute_parameterized_inputs(
    parameterized_project: Dict, parameters: Dict
) -> Dict:
    """Substitutes parameterized r/w inputs

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

    def _get_param_input_match(name, value, access) -> Optional[Match[AnyStr]]:
        if (
            isinstance(value, str)
            and access.get(name, "ReadAndWrite") == "ReadAndWrite"
        ):
            match = variable_pattern.match(value)
            return match
        return None

    for node in project["workbench"].values():
        inputs = node.get("inputs", {})
        access = node.get("inputAccess", {})
        new_inputs = {}

        for name, value in inputs.items():
            match = _get_param_input_match(name, value, access)
            if match:
                # TODO: use jinja2 to interpolate expressions?
                value = match.group(1)
                if value in parameters:
                    new_inputs[name] = _normalize_value(parameters[value])
                else:
                    log.warning(
                        "Could not resolve parameter %s. No value provided in %s",
                        value,
                        parameters,
                    )
        inputs.update(new_inputs)

    return project


def is_graph_equal(
    lhs_workbench: Dict[str, Any], rhs_workbench: Dict[str, Any]
) -> bool:
    """Checks whether both workbench contain the same graph

    Two graphs are the same when the same topology (i.e. nodes and edges)
    and the ports at each node have same values/connections
    """
    try:
        if not set(rhs_workbench.keys()) == set(lhs_workbench.keys()):
            raise ValueError()

        for node_id, node in rhs_workbench.items():
            # same nodes
            if not all(
                node.get(k) == lhs_workbench[node_id].get(k) for k in ["key", "version"]
            ):
                raise ValueError()

            # same connectivity (edges)
            if not set(node.get("inputNodes")) == set(
                lhs_workbench[node_id].get("inputNodes")
            ):
                raise ValueError()

            # same input values
            for port_id, port in node.get("inputs", {}).items():
                if port != lhs_workbench[node_id].get("inputs", {}).get(port_id):
                    raise ValueError()

    except (ValueError, TypeError, AttributeError):
        return False
    return True


async def project_uses_available_services(
    project: Dict[str, Any], available_services: List[Dict[str, Any]]
) -> bool:
    if not project["workbench"]:
        # empty project
        return True
    # get project services
    needed_services: Set[Tuple[str, str]] = {
        (s["key"], s["version"]) for _, s in project["workbench"].items()
    }

    # get available services
    available_services_set: Set[Tuple[str, str]] = {
        (s["key"], s["version"]) for s in available_services
    }

    return needed_services.issubset(available_services_set)


def get_project_unavailable_services(
    project: Dict[str, Any], available_services: List[Dict[str, Any]]
) -> Set[Tuple[str, str]]:
    # get project services
    required: Set[Tuple[str, str]] = {
        (s["key"], s["version"]) for _, s in project["workbench"].items()
    }

    # get available services
    available: Set[Tuple[str, str]] = {
        (s["key"], s["version"]) for s in available_services
    }

    return required - available


async def project_get_depending_nodes(
    project: Dict[str, Any], node_uuid: str
) -> Set[str]:
    depending_node_uuids = set()
    for dep_node_uuid, dep_node_data in project.get("workbench", {}).items():
        for dep_node_inputs_key_data in dep_node_data.get("inputs", {}).values():
            if (
                isinstance(dep_node_inputs_key_data, dict)
                and dep_node_inputs_key_data.get("nodeUuid") == node_uuid
            ):
                depending_node_uuids.add(dep_node_uuid)

    return depending_node_uuids


def extract_dns_without_default_port(url: URL) -> str:
    port = "" if url.port == 80 else f":{url.port}"
    return f"{url.host}{port}"
