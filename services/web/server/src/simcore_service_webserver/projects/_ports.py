from dataclasses import dataclass
from typing import Any, Iterator, Literal, Optional

from models_library.projects_nodes import Node, NodeID

#
#  service/*/ports -> schemas/descriptors CLASS
#  node/*/ports -> values INSTANCE
#


@dataclass
class PortInfo:
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
) -> Iterator[PortInfo]:
    for node_id, node in workbench.items():
        # node representing INPUT ports: can write this node's output
        can_inputs = filter_kind is None or filter_kind == "input"
        can_outputs = filter_kind is None or filter_kind == "output"

        if (
            can_inputs
            and node.key.startswith("simcore/services/frontend/parameter/")
            and node.outputs
        ):
            for output_key in node.outputs.keys():
                # TODO: out_1 always. Can I have more outputs? who guarantees this?
                yield PortInfo(
                    kind="input", node_id=node_id, io_key=output_key, node=node
                )

        # nodes representing OUTPUT ports: can read this node's input
        elif (
            can_outputs
            and node.key.startswith(
                "simcore/services/frontend/iterator-consumer/probe/"
            )
            and node.inputs
        ):
            for inputs_key in node.inputs.keys():
                # TODO: in_1 always. Can I have more outputs? who guarantees this?
                yield PortInfo(
                    kind="output", node_id=node_id, io_key=inputs_key, node=node
                )


def get_project_inputs(workbench: dict[NodeID, Node]) -> dict[NodeID, Any]:
    data = {}
    for port in _iter_project_ports(workbench, "input"):
        data[port.node_id] = port.node.outputs["out_1"] if port.node.outputs else None
    return data


def set_project_inputs(workbench: dict[NodeID, Node], data: dict[NodeID, Any]):
    for node_id, value in data.items():
        # TODO: out_1!??
        workbench[node_id].outputs = {"out_1": value}

    # TODO: returns ALL
    # TODO: what is a port? look for marks check parameters or iterators.
    # TODO: Get schemas from catalog's new ports entry or since they are function-services, perhaps we just import it?? faster??


def get_project_outputs(workbench: dict[NodeID, Node]) -> dict[NodeID, Any]:
    data = {}
    for port in _iter_project_ports(workbench, "output"):
        data[port.node_id] = port.node.inputs["in_1"] if port.node.inputs else None
    return data
