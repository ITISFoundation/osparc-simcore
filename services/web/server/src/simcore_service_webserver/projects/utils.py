import logging
import re
from copy import deepcopy
from re import Match
from typing import Any, TypedDict
from uuid import UUID, uuid1, uuid5

from models_library.projects_nodes_io import NodeIDStr
from models_library.services import ServiceKey
from pydantic import TypeAdapter
from servicelib.decorators import safe_return
from yarl import URL

from .models import ProjectDict

_logger = logging.getLogger(__name__)

_VARIABLE_PATTERN = re.compile(r"^{{\W*(\w+)\W*}}$")

# NOTE: InputTypes/OutputTypes that are NOT links
_NOT_IO_LINK_TYPES_TUPLE = (str, int, float, bool)


class NodeDict(TypedDict, total=False):
    key: ServiceKey | None
    outputs: dict[str, Any] | None


NodesMap = dict[NodeIDStr, NodeIDStr]

_FIELDS_TO_DELETE = ("outputs", "progress", "runHash")


def clone_project_document(
    project: ProjectDict,
    *,
    forced_copy_project_id: UUID | None = None,
    clean_output_data: bool = False,
) -> tuple[ProjectDict, NodesMap]:

    project_copy = deepcopy(project)

    # Update project id
    # NOTE: this can be re-assigned by dbapi if not unique
    if forced_copy_project_id:
        assert isinstance(forced_copy_project_id, UUID)  # nosec
        project_copy_uuid = forced_copy_project_id
    else:
        project_copy_uuid = uuid1()  # random project id

    assert project_copy_uuid  # nosec

    # Change UUID
    project_copy["uuid"] = str(project_copy_uuid)

    # Workbench nodes shall be unique within the project context
    def _create_new_node_uuid(old_uuid) -> NodeIDStr:
        return NodeIDStr(uuid5(project_copy_uuid, str(old_uuid)))

    nodes_map: NodesMap = {}
    for node_uuid in project.get("workbench", {}):
        nodes_map[node_uuid] = _create_new_node_uuid(node_uuid)

    project_map = {project["uuid"]: project_copy["uuid"]}

    def _replace_uuids(node: str | list | dict) -> str | list | dict:
        if isinstance(node, str):
            # NOTE: for datasets we get something like project_uuid/node_uuid/file_id
            if "/" in node:
                parts: list[str] = node.split("/")
                node = "/".join([f"{_replace_uuids(part)}" for part in parts])
            else:
                node = project_map.get(node, nodes_map.get(NodeIDStr(node), node))
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

    if clean_output_data:
        for node_data in project_copy.get("workbench", {}).values():
            for field in _FIELDS_TO_DELETE:
                node_data.pop(field, None)
    return project_copy, nodes_map


@safe_return(if_fails_return=False, logger=_logger)
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

    def _get_param_input_match(name, value, access) -> Match[str] | None:
        if (
            isinstance(value, str)
            and access.get(name, "ReadAndWrite") == "ReadAndWrite"
        ):
            return _VARIABLE_PATTERN.match(value)
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
                    _logger.warning(
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
            raise ValueError

        for node_id, node in rhs_workbench.items():
            # same nodes
            if not all(
                node.get(k) == lhs_workbench[node_id].get(k) for k in ["key", "version"]
            ):
                raise ValueError

            # same connectivity (edges)
            if not set(node.get("inputNodes")) == set(
                lhs_workbench[node_id].get("inputNodes")
            ):
                raise ValueError

            # same input values
            for port_id, port in node.get("inputs", {}).items():
                if port != lhs_workbench[node_id].get("inputs", {}).get(port_id):
                    raise ValueError

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
                _logger.debug(
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
                if not isinstance(input_value, _NOT_IO_LINK_TYPES_TUPLE):
                    _logger.debug(
                        "Change detected in projects[%s].workbench[%s].inputs[%s]=%s. Link was added.",
                        f"{project_uuid=}",
                        f"{node_id=}",
                        f"{input_name}",
                        f"{input_value}",
                    )
                    return True
    return False


_SUPPORTED_FRONTEND_KEYS: set[ServiceKey] = {
    ServiceKey("simcore/services/frontend/file-picker"),
}


def get_frontend_node_outputs_changes(
    new_node: NodeDict, old_node: NodeDict
) -> set[str]:
    changed_keys: set[str] = set()

    # ANE: if node changes it's outputs and is not a supported
    # frontend type, return no frontend changes
    old_key, new_key = old_node.get("key"), new_node.get("key")
    if old_key == new_key and new_key not in _SUPPORTED_FRONTEND_KEYS:
        return set()

    _logger.debug("Comparing nodes %s %s", new_node, old_node)

    def _check_for_changes(d1: dict[str, Any], d2: dict[str, Any]) -> None:
        """
        Checks if d1's values have changed compared to d2's.
        NOTE: Does not guarantee that d2's values have changed
        compare to d1's.
        """
        for k, v in d1.items():
            if k not in d2:
                changed_keys.add(k)
                continue
            if v != d2[k]:
                changed_keys.add(k)

    new_outputs: dict[str, Any] = new_node.get("outputs", {}) or {}
    old_outputs: dict[str, Any] = old_node.get("outputs", {}) or {}

    _check_for_changes(new_outputs, old_outputs)
    _check_for_changes(old_outputs, new_outputs)

    return changed_keys


def find_changed_node_keys(
    current_dict: dict[str, Any],
    new_dict: dict[str, Any],
    *,
    look_for_removed_keys: bool,
) -> dict[str, Any]:
    # The `store` key inside outputs could be either `0` (integer) or `"0"` (string)
    # this generates false positives.
    # Casting to `int` to fix the issue.
    # NOTE: this could make services relying on side effects to stop form propagating
    # changes to downstream connected services.
    # Will only fix the issue for `file-picker` to avoid issues.
    def _cast_outputs_store(dict_data: dict[str, Any]) -> None:
        for data in dict_data.get("outputs", {}).values():
            if "store" in data:
                data["store"] = int(data["store"])

    if current_dict.get("key") == "simcore/services/frontend/file-picker":
        _cast_outputs_store(current_dict)
        _cast_outputs_store(new_dict)

    # start with the missing keys
    changed_keys = {k: new_dict[k] for k in new_dict.keys() - current_dict.keys()}
    if look_for_removed_keys:
        changed_keys.update(
            {k: current_dict[k] for k in current_dict.keys() - new_dict.keys()}
        )
    # then go for the modified ones
    for k in current_dict.keys() & new_dict.keys():
        if current_dict[k] == new_dict[k]:
            continue
        # if the entry was modified put the new one
        modified_entry = {k: new_dict[k]}
        if isinstance(current_dict[k], dict) and isinstance(new_dict[k], dict):
            modified_entry = {
                k: find_changed_node_keys(
                    current_dict[k], new_dict[k], look_for_removed_keys=True
                )
            }
        changed_keys.update(modified_entry)
    return changed_keys


COPY_SUFFIX_RE = re.compile(r"^(.*? \(Copy\))(\(\d+\))?$")
COPY_SUFFIX = "(Copy)"


def default_copy_project_name(name: str) -> str:
    if match := COPY_SUFFIX_RE.fullmatch(name):
        new_copy_index = 1
        if current_copy_index := match.group(2):
            # we receive something of type "(23)"
            new_copy_index = (
                TypeAdapter(int).validate_python(current_copy_index.strip("()")) + 1
            )
        return f"{match.group(1)}({new_copy_index})"
    return f"{name} (Copy)"


def replace_multiple_spaces(text: str) -> str:
    # Use regular expression to replace multiple spaces with a single space
    return re.sub(r"\s+", " ", text)
