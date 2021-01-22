import logging
from typing import Any, Dict, List, Set

import networkx as nx
from models_library.projects import Workbench
from models_library.projects_nodes import NodeID
from models_library.projects_nodes_io import PortLink
from models_library.utils.nodes import compute_node_hash

from .computations import NodeClass, to_node_class
from .logging_utils import log_decorator

logger = logging.getLogger(__file__)


def _mark_node_dirty(
    nodes_data_view: nx.classes.reportviews.NodeDataView, node_id: NodeID
):
    nodes_data_view[str(node_id)]["dirty"] = True


def _is_node_dirty(
    nodes_data_view: nx.classes.reportviews.NodeDataView, node_id: NodeID
) -> bool:
    return nodes_data_view[str(node_id)].get("dirty", False)


def _node_computational(node_key: str) -> bool:
    return to_node_class(node_key) == NodeClass.COMPUTATIONAL


async def _node_outdated(
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
            if _is_node_dirty(nodes_data_view, input_port.node_uuid):
                return True
    # maybe our inputs changed? let's compute the node hash and compare with the saved one
    async def get_node_io_payload_cb(node_id: NodeID) -> Dict[str, Any]:
        return nodes_data_view[str(node_id)]

    computed_hash = await compute_node_hash(node_id, get_node_io_payload_cb)
    return computed_hash != node["run_hash"]


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
async def create_minimal_computational_graph_based_on_selection(
    full_dag_graph: nx.DiGraph, selected_nodes: List[NodeID], force_restart: bool
) -> nx.DiGraph:
    nodes_data_view: nx.classes.reportviews.NodeDataView = full_dag_graph.nodes.data()

    # first pass, find the nodes that are dirty (outdated)
    for node in nx.topological_sort(full_dag_graph):
        if _node_computational(nodes_data_view[node]["key"]) and await _node_outdated(
            nodes_data_view, node
        ):
            _mark_node_dirty(nodes_data_view, node)

    # second pass, detect all the nodes that need to be run
    minimal_selection_nodes: Set[NodeID] = set()
    if not selected_nodes:
        # fully automatic detection, we want anything that is outdated or depending on outdated nodes
        minimal_selection_nodes.update(
            {
                n
                for n, _ in nodes_data_view
                if _node_computational(nodes_data_view[n]["key"])
                and (force_restart or _is_node_dirty(nodes_data_view, n))
            }
        )
    else:
        # we want all the outdated nodes that are in the tree leading to the selected nodes
        for node in selected_nodes:
            minimal_selection_nodes.update(
                set(
                    n
                    for n in nx.bfs_tree(full_dag_graph, str(node), reverse=True)
                    if _node_computational(nodes_data_view[n]["key"])
                    and (force_restart or _is_node_dirty(nodes_data_view, n))
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
