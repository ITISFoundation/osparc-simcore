from dataclasses import dataclass
from typing import Any, Iterator, Literal, Optional

from models_library.projects_nodes import Node, NodeID
from models_library.projects_nodes_io import PortLink
from pydantic import ValidationError

#
#  service/*/ports -> schemas/descriptors CLASS
#  node/*/ports -> values INSTANCE
#


@dataclass
class _ProjectPort:
    kind: Literal["input", "output"]
    node_id: NodeID
    io_key: str
    node: Node

    @property
    def key(self):
        return f"{self.node_id}.{self.io_key}"


def _iter_project_ports(
    workbench: dict[NodeID, Node],
    filter_kind: Optional[Literal["input", "output"]] = None,
) -> Iterator[_ProjectPort]:
    """Iterates the nodes in a workbench that define the input/output ports of a project

    - A node in general has inputs and outputs:
      - Inputs can have values or references.
      - Outputs have only values (TODO:  verify!! )

    - A project defines its ports with special nodes:
        - An input node: has no inputs and stores its value as an output
        - An output node: has not outputs and stores a reference to an output in his input
    """

    for node_id, node in workbench.items():
        is_inputs = filter_kind is None or filter_kind == "input"
        is_outputs = filter_kind is None or filter_kind == "output"

        # node representing INPUT ports: can write this node's output
        if (
            is_inputs
            and node.key.startswith("simcore/services/frontend/parameter/")
            and node.outputs
        ):
            # invariants
            assert not node.inputs  # nosec
            assert list(node.outputs.keys()) == ["out_1"]  # nosec

            for output_key in node.outputs.keys():
                # TODO: out_1 always. Can I have more outputs? who guarantees this?
                yield _ProjectPort(
                    kind="input", node_id=node_id, io_key=output_key, node=node
                )

        # nodes representing OUTPUT ports: can read this node's input
        elif (
            is_outputs
            and node.key.startswith(
                "simcore/services/frontend/iterator-consumer/probe/"
            )
            and node.inputs
        ):
            # invariants
            assert not node.outputs  # nosec
            assert list(node.inputs.keys()) == ["in_1"]  # nosec

            for inputs_key in node.inputs.keys():
                # TODO: in_1 always. Can I have more outputs? who guarantees this?
                yield _ProjectPort(
                    kind="output", node_id=node_id, io_key=inputs_key, node=node
                )


def get_project_inputs(workbench: dict[NodeID, Node]) -> dict[NodeID, Any]:
    """Returns the values assigned to each input node"""
    input_to_value = {}
    for port in _iter_project_ports(workbench, "input"):
        input_to_value[port.node_id] = (
            port.node.outputs["out_1"] if port.node.outputs else None
        )
    return input_to_value


def set_project_inputs(
    workbench: dict[NodeID, Node], update: dict[NodeID, Any]
) -> None:
    """Updates selected input nodes"""
    # TODO: add schema validation!
    for node_id, value in update.items():
        workbench[node_id].outputs = {"out_1": value}

    #
    # TODO: returns ALL
    # TODO: Get schemas from catalog's new ports entry or since they are function-services, perhaps we just import it?? faster??


class _PortLink(PortLink):
    class Config(PortLink.Config):
        allow_population_by_field_name = True


def get_project_outputs(workbench: dict[NodeID, Node]) -> dict[NodeID, Any]:
    """Returns values assigned to each output node"""
    output_to_value = {}
    for port in _iter_project_ports(workbench, "output"):
        if port.node.inputs:
            try:
                # is link?
                port_link = _PortLink.parse_obj(port.node.inputs["in_1"])
                # resolve
                node = workbench[port_link.node_uuid]
                # might still not have results
                value = node.outputs[port_link.output] if node.outputs else None
            except ValidationError:
                # not a link
                value = port.node.inputs["in_1"]
        else:
            value = None

        output_to_value[port.node_id] = value
    return output_to_value
