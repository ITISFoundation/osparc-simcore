import logging
from typing import List

import networkx as nx
from models_library.nodes import NodeID
from models_library.projects import Workbench

from .computations import to_node_class, NodeClass

log = logging.getLogger(__file__)


def find_entrypoints(graph: nx.DiGraph) -> List[NodeID]:
    entrypoints = [n for n in graph.nodes if not list(graph.predecessors(n))]
    log.debug("the entrypoints of the graph are %s", entrypoints)
    return entrypoints


def create_dag_graph(workbench: Workbench) -> nx.DiGraph:
    dag_graph = nx.DiGraph()
    for node_id, node in workbench.items():
        if to_node_class(node.key) == NodeClass.COMPUTATIONAL:
            dag_graph.add_node(
                node_id, name=node.label, key=node.key, version=node.version
            )
            for input_node_id in node.inputNodes:
                predecessor_node = workbench.get(str(input_node_id))
                if (
                    predecessor_node
                    and to_node_class(predecessor_node.key) == NodeClass.COMPUTATIONAL
                ):
                    dag_graph.add_edge(input_node_id, node_id)
    log.debug("created DAG graph: %s", nx.to_dict_of_lists(dag_graph))

    return dag_graph


def topological_sort_grouping(dag_graph: nx.DiGraph) -> List:
    # copy the graph
    graph_copy = dag_graph.copy()
    res = []
    while graph_copy:
        zero_indegree = [v for v, d in graph_copy.in_degree() if d == 0]
        res.append(zero_indegree)
        graph_copy.remove_nodes_from(zero_indegree)
    return res
