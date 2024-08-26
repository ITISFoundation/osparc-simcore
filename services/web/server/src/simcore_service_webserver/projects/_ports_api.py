from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, Literal, NamedTuple

from aiohttp import web
from models_library.api_schemas_directorv2.comp_tasks import (
    OutputName,
    TasksOutputs,
    TasksSelection,
)
from models_library.basic_types import IDStr, KeyIDStr
from models_library.function_services_catalog.api import (
    catalog,
    is_parameter_service,
    is_probe_service,
)
from models_library.projects import ProjectID
from models_library.projects_nodes import Node, OutputsDict
from models_library.projects_nodes_io import NodeID, PortLink
from models_library.services_io import ServiceInput, ServiceOutput
from models_library.services_types import ServicePortKey
from models_library.utils.json_schema import (
    JsonSchemaValidationError,
    jsonschema_validate_data,
)
from models_library.utils.services_io import JsonSchemaDict, get_service_io_json_schema
from pydantic import ValidationError

from ..director_v2.api import get_batch_tasks_outputs
from .exceptions import InvalidInputValue


@dataclass(frozen=True)
class ProjectPortData:
    kind: Literal["input", "output"]
    node_id: NodeID
    io_key: ServicePortKey
    node: Node

    @property
    def key(self):
        return f"{self.node_id}.{self.io_key}"

    def get_schema(self) -> JsonSchemaDict | None:
        node_meta = catalog.get_metadata(self.node.key, self.node.version)
        if (
            self.kind == "input"
            and node_meta.outputs
            and (input_meta := node_meta.outputs[self.io_key])
        ):
            return self._get_port_schema(input_meta)
        if (
            self.kind == "output"
            and node_meta.inputs
            and (output_meta := node_meta.inputs[self.io_key])
        ):
            return self._get_port_schema(output_meta)
        return None

    def _get_port_schema(
        self, io_meta: ServiceInput | ServiceOutput
    ) -> JsonSchemaDict | None:
        schema = get_service_io_json_schema(io_meta)
        if schema:
            # uses node label instead of service title
            # This way it will contain the label the user
            # gave to the port
            schema["title"] = self.node.label
        return schema


def iter_project_ports(
    workbench: dict[NodeID, Node],
    filter_kind: Literal["input", "output"] | None = None,
) -> Iterator[ProjectPortData]:
    """Iterates the nodes in a workbench that define the input/output ports of a project

    - A node in general has inputs and outputs:
      - Inputs can have values or references.
      - Outputs have only values

    - A project defines its ports with special nodes:
        - An input node: has no inputs and stores its value as an output
        - An output node: has not outputs and stores a reference to an output in his input
    """

    for node_id, node in workbench.items():
        is_input = filter_kind is None or filter_kind == "input"
        is_output = filter_kind is None or filter_kind == "output"

        # node representing INPUT ports: can write this node's output
        if is_input and is_parameter_service(node.key) and node.outputs:
            assert not node.inputs  # nosec
            assert list(node.outputs.keys()) == ["out_1"]  # nosec

            for output_key in node.outputs:
                yield ProjectPortData(
                    kind="input",
                    node_id=node_id,
                    io_key=ServicePortKey(
                        output_key
                    ),  # NOTE: PC: ServicePortKey and KeyIDStr are the same why do we need both?
                    node=node,
                )

        # nodes representing OUTPUT ports: can read this node's input
        elif is_output and is_probe_service(node.key) and node.inputs:
            assert not node.outputs  # nosec
            assert list(node.inputs.keys()) == ["in_1"]  # nosec

            for inputs_key in node.inputs:
                yield ProjectPortData(
                    kind="output",
                    node_id=node_id,
                    io_key=ServicePortKey(
                        inputs_key
                    ),  # NOTE: PC: ServicePortKey and KeyIDStr are the same why do we need both?
                    node=node,
                )


def get_project_inputs(workbench: dict[NodeID, Node]) -> dict[NodeID, Any]:
    """Returns the values assigned to each input node"""
    input_to_value = {}
    for port in iter_project_ports(workbench, "input"):
        input_to_value[port.node_id] = (
            port.node.outputs[KeyIDStr("out_1")] if port.node.outputs else None
        )
    return input_to_value


def set_inputs_in_project(
    workbench: dict[NodeID, Node], update: dict[NodeID, Any]
) -> set[NodeID]:
    """Updates selected input nodes and
    Returns the ids of nodes that actually changed

    raises InvalidInputValue
    """
    modified = set()
    for node_id, value in update.items():
        output: OutputsDict = {KeyIDStr("out_1"): value}

        if (node := workbench[node_id]) and node.outputs != output:
            # validates value against jsonschema
            try:
                port = ProjectPortData(
                    kind="input",
                    node_id=node_id,
                    io_key=ServicePortKey("out_1"),
                    node=node,
                )
                if schema := port.get_schema():
                    jsonschema_validate_data(value, schema)
            except JsonSchemaValidationError as err:
                raise InvalidInputValue(
                    node_id=node_id, message=err.message, value=value
                ) from err

            workbench[node_id].outputs = output
            modified.add(node_id)
    return modified


class _NonStrictPortLink(PortLink):
    class Config(PortLink.Config):
        allow_population_by_field_name = True


class _OutputPortInfo(NamedTuple):
    port_node_id: NodeID  # a probe node
    task_node_id: NodeID  # a computational node
    task_output_name: str  # an output of the computation node
    task_output_in_workbench: Any  # the valud in the workbench of a computational node


def _get_outputs_in_workbench(workbench: dict[NodeID, Node]) -> dict[NodeID, Any]:
    """Get the outputs values in the workbench associated to every output"""
    output_to_value: dict[NodeID, Any] = {}
    for port in iter_project_ports(workbench, "output"):
        if port.node.inputs:
            try:
                # Every port is associated to the output of a task
                port_link = _NonStrictPortLink.parse_obj(
                    port.node.inputs[KeyIDStr("in_1")]
                )
                # Here we resolve which task and which tasks' output is associated to this port?
                task_node_id = port_link.node_uuid
                task_output_name = port_link.output
                task_node = workbench[task_node_id]
                output_to_value[port.node_id] = _OutputPortInfo(
                    port_node_id=port.node_id,
                    task_node_id=task_node_id,
                    task_output_name=task_output_name,
                    task_output_in_workbench=(
                        # If the node has not results (e.g. did not run or failed),
                        # then node.outputs is set to None. NOTE that `{}`` might be a result
                        task_node.outputs.get(task_output_name)
                        if task_node.outputs is not None
                        else None
                    ),
                )
            except ValidationError:
                # not a link
                output_to_value[port.node_id] = port.node.inputs[KeyIDStr("in_1")]
        else:
            output_to_value[port.node_id] = None

    return output_to_value


async def _get_computation_tasks_outputs(
    app: web.Application, *, project_id: ProjectID, nodes_ids: set[NodeID]
) -> dict[NodeID, dict[OutputName, Any]]:
    selection = TasksSelection(nodes_ids=list(nodes_ids))
    batch: TasksOutputs = await get_batch_tasks_outputs(
        app, project_id=project_id, selection=selection
    )
    return batch.nodes_outputs


async def get_project_outputs(
    app: web.Application, *, project_id: ProjectID, workbench: dict[NodeID, Node]
) -> dict[NodeID, Any]:

    # WARNING: these NodeIDs are the port nodes!!
    outputs_map_in_workbench: dict[NodeID, Any] = _get_outputs_in_workbench(workbench)

    # Get NodeIDs of the computational nodes
    task_node_ids = set()
    for v in outputs_map_in_workbench.values():
        if isinstance(v, _OutputPortInfo):
            task_node_ids.add(v.task_node_id)

    # Updates previous results with task computations to avoid issue https://github.com/ITISFoundation/osparc-simcore/pull/5721
    tasks_outputs = await _get_computation_tasks_outputs(
        app, project_id=project_id, nodes_ids=task_node_ids
    )

    outputs_map: dict[NodeID, Any] = {}
    for port_node_id, v in outputs_map_in_workbench.items():
        if isinstance(v, _OutputPortInfo):
            assert v.port_node_id == port_node_id  # nosec
            outputs_map[port_node_id] = tasks_outputs[v.task_node_id].get(
                IDStr(v.task_output_name), v.task_output_in_workbench
            )

    return outputs_map
