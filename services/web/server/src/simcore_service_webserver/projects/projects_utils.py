import logging
import re
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, AnyStr, Match, Optional, Union
from uuid import UUID, uuid1, uuid5

from servicelib.decorators import safe_return
from models_library.services import ServiceKey
from yarl import URL

from .project_models import ProjectDict

log = logging.getLogger(__name__)

VARIABLE_PATTERN = re.compile(r"^{{\W*(\w+)\W*}}$")

# NOTE: InputTypes/OutputTypes that are NOT links
NOT_IO_LINK_TYPES_TUPLE = (str, int, float, bool)


@dataclass
class OutputsChanges:
    changed: bool
    keys: set[str]


def clone_project_document(
    project: dict,
    *,
    forced_copy_project_id: Optional[UUID] = None,
    clean_output_data: bool = False,
) -> tuple[dict, dict]:
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

    def _replace_uuids(node: Union[str, list, dict]) -> Union[str, list, dict]:
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
    parameterized_project: dict, parameters: dict
) -> dict:
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
            match = VARIABLE_PATTERN.match(value)
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
    lhs_workbench: dict[str, Any], rhs_workbench: dict[str, Any]
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
    project: dict[str, Any], available_services: list[dict[str, Any]]
) -> bool:
    if not project["workbench"]:
        # empty project
        return True
    # get project services
    needed_services: set[tuple[str, str]] = {
        (s["key"], s["version"]) for _, s in project["workbench"].items()
    }

    # get available services
    available_services_set: set[tuple[str, str]] = {
        (s["key"], s["version"]) for s in available_services
    }

    return needed_services.issubset(available_services_set)


def get_project_unavailable_services(
    project: dict[str, Any], available_services: list[dict[str, Any]]
) -> set[tuple[str, str]]:
    # get project services
    required: set[tuple[str, str]] = {
        (s["key"], s["version"]) for _, s in project["workbench"].items()
    }

    # get available services
    available: set[tuple[str, str]] = {
        (s["key"], s["version"]) for s in available_services
    }

    return required - available


async def project_get_depending_nodes(
    project: dict[str, Any], node_uuid: str
) -> set[str]:
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


def any_node_inputs_changed(
    updated_project: ProjectDict, current_project: ProjectDict
) -> bool:
    """Returns true if any change is detected in the node inputs of the updated project

    Based on the limitation we are detecting with this check, new nodes only account for
    a "change" if they add link inputs.
    """
    # NOTE: should not raise exceptions in production

    project_uuid = current_project["uuid"]

    assert (  # nosec
        updated_project.get("uuid") == project_uuid
    ), f"Expected same project, got {updated_project.get('uuid')}!={project_uuid}"

    assert (  # nosec
        "workbench" in updated_project
    ), f"expected validated model but got {list(updated_project.keys())=}"

    assert (  # nosec
        "workbench" in current_project
    ), f"expected validated model but got {list(current_project.keys())=}"

    # detect input changes in existing nodes
    for node_id, updated_node in updated_project["workbench"].items():
        if current_node := current_project["workbench"].get(node_id, None):
            if (updated_inputs := updated_node.get("inputs")) != current_node.get(
                "inputs"
            ):
                log.debug(
                    "Change detected in projects[%s].workbench[%s].%s",
                    f"{project_uuid=}",
                    f"{node_id=}",
                    f"{updated_inputs=}",
                )
                return True

        else:
            # for new nodes, detect only added link
            for input_name, input_value in updated_node.get("inputs", {}).items():
                # TODO: how to ensure this list of "links types" is up-to-date!??
                # Anything outside of the PRIMITIVE_TYPES_TUPLE, is interpreted as links
                # that node-ports need to handle. This is a simpler check with ProjectDict
                # since otherwise test will require constructing BaseModels on input_values
                if not isinstance(input_value, NOT_IO_LINK_TYPES_TUPLE):
                    log.debug(
                        "Change detected in projects[%s].workbench[%s].inputs[%s]=%s. Link was added.",
                        f"{project_uuid=}",
                        f"{node_id=}",
                        f"{input_name}",
                        f"{input_value}",
                    )
                    return True
    return False


def get_node_outputs_changes(
    new_node: dict[str, Any], old_node: dict[str, Any], filter_keys: set[ServiceKey]
) -> OutputsChanges:
    """if node is a specific type it checks if outputs changed"""
    nodes_keys = {old_node.get("key"), new_node.get("key")}
    if not (len(nodes_keys) == 1 and nodes_keys.pop() in filter_keys):
        return OutputsChanges(changed=False, keys=set())

    log.debug("Comparing nodes %s %s", new_node, old_node)
    outputs_changed = new_node.get("outputs") != old_node.get("outputs")

    def _get_outputs_keys(node_data: dict[str, Any]) -> set[str]:
        outputs = node_data.get("outputs", {})
        if outputs is None:
            return set()
        return set(outputs.keys())

    changed_keys = _get_outputs_keys(new_node).symmetric_difference(
        _get_outputs_keys(old_node)
    )
    return OutputsChanges(changed=outputs_changed, keys=changed_keys)
