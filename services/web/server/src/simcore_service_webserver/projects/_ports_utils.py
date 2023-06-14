from dataclasses import dataclass
from typing import Any, Iterator, Literal

from models_library.function_services_catalog.api import catalog
from models_library.projects_nodes import Node, NodeID
from models_library.projects_nodes_io import PortLink
from models_library.utils.json_schema import (
    JsonSchemaValidationError,
    jsonschema_validate_data,
)
from models_library.utils.services_io import JsonSchemaDict, get_service_io_json_schema
from pydantic import ValidationError


@dataclass(frozen=True)
class ProjectPortData:
    kind: Literal["input", "output"]
    node_id: NodeID
    io_key: str
    node: Node

    @property
    def key(self):
        return f"{self.node_id}.{self.io_key}"

    def get_schema(self) -> JsonSchemaDict | None:
        node_meta = catalog.get_metadata(self.node.key, self.node.version)
        if self.kind == "input" and node_meta.outputs:
            if input_meta := node_meta.outputs[self.io_key]:
                return self._get_port_schema(input_meta)
        elif self.kind == "output" and node_meta.inputs:
            if output_meta := node_meta.inputs[self.io_key]:
                return self._get_port_schema(output_meta)
        return None

    def _get_port_schema(self, io_meta):
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
        if (
            is_input
            and node.key.startswith("simcore/services/frontend/parameter/")
            and node.outputs
        ):
            assert not node.inputs  # nosec
            assert list(node.outputs.keys()) == ["out_1"]  # nosec

            for output_key in node.outputs.keys():
                yield ProjectPortData(
                    kind="input", node_id=node_id, io_key=output_key, node=node
                )

        # nodes representing OUTPUT ports: can read this node's input
        elif (
            is_output
            and node.key.startswith(
                "simcore/services/frontend/iterator-consumer/probe/"
            )
            and node.inputs
        ):
            assert not node.outputs  # nosec
            assert list(node.inputs.keys()) == ["in_1"]  # nosec

            for inputs_key in node.inputs.keys():
                yield ProjectPortData(
                    kind="output", node_id=node_id, io_key=inputs_key, node=node
                )


def get_project_inputs(workbench: dict[NodeID, Node]) -> dict[NodeID, Any]:
    """Returns the values assigned to each input node"""
    input_to_value = {}
    for port in iter_project_ports(workbench, "input"):
        input_to_value[port.node_id] = (
            port.node.outputs["out_1"] if port.node.outputs else None
        )
    return input_to_value


class InvalidInputValue(ValueError):
    pass


def set_project_inputs(
    workbench: dict[NodeID, Node], update: dict[NodeID, Any]
) -> set[NodeID]:
    """Updates selected input nodes and
    Returns the ids of nodes that actually changed

    raises InvalidInputValue
    """
    modified = set()
    for node_id, value in update.items():
        output = {"out_1": value}

        if (node := workbench[node_id]) and node.outputs != output:
            # validates value against jsonschema
            try:
                port = ProjectPortData(
                    kind="input", node_id=node_id, io_key="out_1", node=node
                )
                if schema := port.get_schema():
                    jsonschema_validate_data(value, schema)
            except JsonSchemaValidationError as err:
                raise InvalidInputValue(
                    f"Invalid value for input '{node_id}': {err.message} for {value=}"
                ) from err

            workbench[node_id].outputs = output
            modified.add(node_id)
    return modified


class _NonStrictPortLink(PortLink):
    class Config(PortLink.Config):
        allow_population_by_field_name = True


def get_project_outputs(workbench: dict[NodeID, Node]) -> dict[NodeID, Any]:
    """Returns values assigned to each output node"""
    output_to_value = {}
    for port in iter_project_ports(workbench, "output"):
        if port.node.inputs:
            try:
                # Is link?
                port_link = _NonStrictPortLink.parse_obj(port.node.inputs["in_1"])
                # resolve
                node = workbench[port_link.node_uuid]
                # If the node has not results (e.g. did not run or failed), then node.outputs is set to None
                value = node.outputs[port_link.output] if node.outputs else None
            except ValidationError:
                # not a link
                value = port.node.inputs["in_1"]
        else:
            value = None

        output_to_value[port.node_id] = value
    return output_to_value
