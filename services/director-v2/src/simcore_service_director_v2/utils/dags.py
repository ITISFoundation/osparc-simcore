import hashlib
import json
import logging
from copy import deepcopy
from typing import Dict, List, Set

import networkx as nx
from models_library.projects import Workbench
from models_library.projects_nodes import Inputs, NodeID, Outputs
from models_library.projects_nodes_io import PortLink
from pydantic.main import BaseModel

from .computations import NodeClass, to_node_class
from .logging_utils import log_decorator

logger = logging.getLogger(__file__)


@log_decorator(logger=logger)
def find_entrypoints(graph: nx.DiGraph) -> List[NodeID]:
    entrypoints = [n for n in graph.nodes if not list(graph.predecessors(n))]
    logger.debug("the entrypoints of the graph are %s", entrypoints)
    return entrypoints


@log_decorator(logger=logger)
def create_complete_dag_graph(workbench: Workbench) -> nx.DiGraph:
    """creates a complete graph out of the project workbench"""
    dag_graph = nx.DiGraph()
    for node_id, node in workbench.items():
        dag_graph.add_node(
            node_id,
            name=node.label,
            key=node.key,
            version=node.version,
            inputs=node.inputs,
            run_hash=node.run_hash,
            outputs=node.outputs,
        )
        for input_node_id in node.input_nodes:
            predecessor_node = workbench.get(str(input_node_id))
            if predecessor_node:
                dag_graph.add_edge(str(input_node_id), node_id)

    return dag_graph


@log_decorator(logger=logger)
def create_complete_computational_dag_graph(workbench: Workbench) -> nx.DiGraph:
    """creates a graph containing only computational nodes"""
    dag_graph = nx.DiGraph()
    for node_id, node in workbench.items():
        if _node_computational(node.key):
            dag_graph.add_node(
                node_id,
                name=node.label,
                key=node.key,
                version=node.version,
                inputs=node.inputs,
                run_hash=node.run_hash,
                outputs=node.outputs,
            )
            for input_node_id in node.input_nodes:
                predecessor_node = workbench.get(str(input_node_id))
                if predecessor_node and _node_computational(predecessor_node.key):
                    dag_graph.add_edge(str(input_node_id), node_id)

    return dag_graph


def mark_node_dirty(
    nodes_data_view: nx.classes.reportviews.NodeDataView, node_id: NodeID
):
    nodes_data_view[str(node_id)]["dirty"] = True


def is_node_dirty(
    nodes_data_view: nx.classes.reportviews.NodeDataView, node_id: NodeID
) -> bool:
    # FIXME: this fails if the node we check is not a computational one!!!
    return nodes_data_view[str(node_id)].get("dirty", False)


def _node_computational(node_key: str) -> bool:
    return to_node_class(node_key) == NodeClass.COMPUTATIONAL


def _compute_node_hash(
    nodes_data_view: nx.classes.reportviews.NodeDataView, node_id: NodeID
) -> str:
    node_inputs = nodes_data_view[str(node_id)]["inputs"]
    node_outputs = nodes_data_view[str(node_id)]["outputs"]
    # resolve the port links if any
    resolved_inputs = {}
    for input_key, input_value in node_inputs.items():
        payload = input_value
        if isinstance(input_value, PortLink):
            # let's resolve the entry
            previous_node = nodes_data_view[str(input_value.node_uuid)]
            previous_node_outputs = previous_node.get("outputs", {})
            payload = previous_node_outputs.get(input_value.output)
        if payload is not None:
            resolved_inputs[input_key] = payload

    io_payload = {"inputs": resolved_inputs, "outputs": node_outputs}

    class PydanticEncoder(json.JSONEncoder):
        def default(self, o):
            if isinstance(o, BaseModel):
                return o.dict(by_alias=True, exclude_unset=True)
            return json.JSONEncoder.default(self, o)

    block_string = json.dumps(io_payload, cls=PydanticEncoder).encode("utf-8")
    raw_hash = hashlib.sha256(block_string)
    return raw_hash.hexdigest()


def _node_outdated(
    nodes_data_view: nx.classes.reportviews.NodeDataView, node_id: NodeID
) -> bool:
    node = nodes_data_view[str(node_id)]
    # if the node has no output it is outdated for sure
    if not node["outputs"]:
        return True
    for output_port in node["outputs"]:
        if output_port is None:
            return True
    # check if the previous node (if any) are dirty... in which case this one is too
    for input_port in node["inputs"].values():
        if isinstance(input_port, PortLink):
            if is_node_dirty(nodes_data_view, input_port.node_uuid):
                return True
    # maybe our inputs changed? let's compute the node hash and compare with the saved one
    computed_hash = _compute_node_hash(nodes_data_view, node_id)
    return computed_hash != node["run_hash"]


@log_decorator(logger=logger)
def create_minimal_computational_graph_based_on_selection(
    full_dag_graph: nx.DiGraph, selected_nodes: List[NodeID]
) -> nx.DiGraph:
    nodes_data_view: nx.classes.reportviews.NodeDataView = full_dag_graph.nodes.data()
    selected_nodes_str = [str(n) for n in selected_nodes]

    # first pass, find the nodes that are dirty (outdated)
    for node in nx.topological_sort(full_dag_graph):
        if (
            node in selected_nodes_str
            or _node_outdated(nodes_data_view, node)
            and _node_computational(nodes_data_view[node]["key"])
        ):
            mark_node_dirty(nodes_data_view, node)

    # now we want all the outdated nodes that are in the tree from the selected nodes
    minimal_selection_nodes: Set[NodeID] = set()
    for node in selected_nodes:
        minimal_selection_nodes.update(
            set(
                n
                for n in nx.bfs_tree(full_dag_graph, str(node), reverse=True)
                if is_node_dirty(nodes_data_view, n)
                and _node_computational(nodes_data_view[n]["key"])
            )
        )

    return full_dag_graph.subgraph(minimal_selection_nodes)


@log_decorator(logger=logger)
def topological_sort_grouping(dag_graph: nx.DiGraph) -> List:
    # copy the graph
    graph_copy = dag_graph.copy()
    res = []
    while graph_copy:
        zero_indegree = [v for v, d in graph_copy.in_degree() if d == 0]
        res.append(zero_indegree)
        graph_copy.remove_nodes_from(zero_indegree)
    return res
