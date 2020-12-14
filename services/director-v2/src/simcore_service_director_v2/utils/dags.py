import logging
from typing import List, Set

import networkx as nx
from models_library.projects import Workbench
from models_library.projects_nodes import NodeID
from models_library.projects_nodes_io import PortLink

from .computations import NodeClass, to_node_class
from .logging_utils import log_decorator

logger = logging.getLogger(__file__)


@log_decorator(logger=logger)
def find_entrypoints(graph: nx.DiGraph) -> List[NodeID]:
    entrypoints = [n for n in graph.nodes if not list(graph.predecessors(n))]
    logger.debug("the entrypoints of the graph are %s", entrypoints)
    return entrypoints


@log_decorator(logger=logger)
def create_dag_graph(workbench: Workbench) -> nx.DiGraph:
    dag_graph = nx.DiGraph()
    for node_id, node in workbench.items():
        if to_node_class(node.key) == NodeClass.COMPUTATIONAL:
            dag_graph.add_node(
                node_id,
                name=node.label,
                key=node.key,
                version=node.version,
                inputs=node.inputs,
                outputs=node.outputs,
            )
            for input_node_id in node.input_nodes:
                predecessor_node = workbench.get(str(input_node_id))
                if (
                    predecessor_node
                    and to_node_class(predecessor_node.key) == NodeClass.COMPUTATIONAL
                ):
                    dag_graph.add_edge(str(input_node_id), node_id)

    return dag_graph


def mark_node_dirty(graph: nx.DiGraph, node_id: NodeID):
    graph.nodes()[str(node_id)]["dirty"] = True


def is_node_dirty(graph: nx.DiGraph, node_id: NodeID) -> bool:
    return graph.nodes()[str(node_id)].get("dirty", False)


def _node_outdated(full_dag_graph: nx.DiGraph, node_id: NodeID) -> bool:
    node = full_dag_graph.nodes(data=True)[str(node_id)]
    # if the node has no output it is outdated for sure
    if not node["outputs"]:
        return True
    for output_port in node["outputs"]:
        if output_port is None:
            return True
    # ok so we have outputs, but maybe the inputs are old? let's check recursively
    for input_port in node["inputs"]:
        if isinstance(input_port, PortLink):
            if is_node_dirty(full_dag_graph, input_port.node_uuid):
                return True
        else:
            # FIXME: here we should check if the current inputs are the ones used to generate the current outputs
            # this could be done by saving the inputs as metadata together with the outputs (see blockchain)
            # we should compare the current inputs with the inputs used for generating the current outputs!!!
            pass
    return False


@log_decorator(logger=logger)
def create_minimal_graph_based_on_selection(
    full_dag_graph: nx.DiGraph, selected_nodes: Set[NodeID]
) -> nx.DiGraph:
    # first pass, set the dirty attribute on the graph
    for node in nx.topological_sort(full_dag_graph):
        if node in selected_nodes or _node_outdated(full_dag_graph, node):
            mark_node_dirty(full_dag_graph, node)

    # now we want all the outdated nodes that are in the tree from the selected nodes
    minimal_selection_nodes: Set[NodeID] = set()
    for node in selected_nodes:
        minimal_selection_nodes.update(
            set(
                n
                for n in nx.bfs_tree(full_dag_graph, str(node), reverse=True)
                if is_node_dirty(full_dag_graph, n)
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
