import logging
from typing import List, Set

import networkx as nx
from models_library.projects import Workbench
from models_library.projects_nodes import NodeID

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
                node_id, name=node.label, key=node.key, version=node.version
            )
            for input_node_id in node.input_nodes:
                predecessor_node = workbench.get(str(input_node_id))
                if (
                    predecessor_node
                    and to_node_class(predecessor_node.key) == NodeClass.COMPUTATIONAL
                ):
                    dag_graph.add_edge(str(input_node_id), node_id)

    return dag_graph


@log_decorator(logger=logger)
def create_minimal_graph_based_on_selection(
    workbench: Workbench, full_dag_graph: nx.DiGraph, selected_nodes: Set[NodeID]
) -> nx.DiGraph:
    # find depending nodes (if their linked output is missing, they should be run as well)
    for node in selected_nodes:
        # get list of predecessors of that node (will return only first degree)
        for parent_node in full_dag_graph.predecessors(node):
            pass

    return full_dag_graph.subgraph(selected_nodes)


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
