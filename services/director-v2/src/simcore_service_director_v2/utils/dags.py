import logging
from enum import Enum
from typing import Any, Dict, List, Set

import networkx as nx
from models_library.projects import Workbench
from models_library.projects_nodes import NodeID
from models_library.projects_nodes_io import PortLink
from models_library.utils.nodes import compute_node_hash
from simcore_service_director_v2.models.domains.comp_tasks import CompTaskAtDB

from ..models.schemas.comp_tasks import (
    NodeIOState,
    NodeRunnableState,
    NodeState,
    PipelineDetails,
)
from .computations import NodeClass, to_node_class
from .logging_utils import log_decorator

logger = logging.getLogger(__file__)


def _is_node_computational(node_key: str) -> bool:
    return to_node_class(node_key) == NodeClass.COMPUTATIONAL


def _mark_node_as_dirty(
    nodes_data_view: nx.classes.reportviews.NodeDataView, node_id: NodeID
):
    nodes_data_view[str(node_id)]["dirty"] = True


def _is_node_dirty(
    nodes_data_view: nx.classes.reportviews.NodeDataView, node_id: NodeID
) -> bool:
    return nodes_data_view[str(node_id)].get("dirty", False)


async def _is_node_outdated(
    nodes_data_view: nx.classes.reportviews.NodeDataView, node_id: NodeID
) -> bool:
    """this function will return whether a node is outdated:
    - if it has no outputs
    - if one of the output ports in the outputs is missing
    - if, after *resolving the inputs if linked to other nodes* these nodes are dirty (outdated themselves)
    - if the last run_hash does not fit with the current one
    """
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
def create_complete_dag(workbench: Workbench) -> nx.DiGraph:
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
def create_complete_dag_from_tasks(tasks: List[CompTaskAtDB]) -> nx.DiGraph:
    dag_graph = nx.DiGraph()
    for task in tasks:
        dag_graph.add_node(
            str(task.node_id),
            name=task.job_id,
            key=task.image.name,
            version=task.image.tag,
            inputs=task.inputs,
            run_hash=task.run_hash,
            outputs=task.outputs,
        )
        for input_data in task.inputs.values():
            if isinstance(input_data, PortLink):
                dag_graph.add_edge(str(input_data.node_uuid), str(task.node_id))
    return dag_graph


async def compute_node_io_state(
    nodes_data_view: nx.classes.reportviews.NodeDataView, node_id: NodeID
) -> NodeIOState:
    node = nodes_data_view[str(node_id)]
    # if the node has no output it is outdated for sure
    if not node["outputs"]:
        return NodeIOState.OUTDATED
    for output_port in node["outputs"]:
        if output_port is None:
            return NodeIOState.OUTDATED
    # maybe our inputs changed? let's compute the node hash and compare with the saved one
    async def get_node_io_payload_cb(node_id: NodeID) -> Dict[str, Any]:
        return nodes_data_view[str(node_id)]

    computed_hash = await compute_node_hash(node_id, get_node_io_payload_cb)
    if computed_hash != node["run_hash"]:
        return NodeIOState.OUTDATED
    return NodeIOState.OK


async def compute_node_runnable_state(nodes_data_view, node_id) -> NodeRunnableState:
    node = nodes_data_view[str(node_id)]
    # check if the previous node is outdated or waits for dependencies... in which case this one has to wait
    for input_port in node.get("inputs", {}).values():
        if isinstance(input_port, PortLink):
            if node_needs_computation(nodes_data_view, input_port.node_uuid):
                return NodeRunnableState.WAITING_FOR_DEPENDENCIES
    # all good. ready
    return NodeRunnableState.READY


async def compute_node_states(
    nodes_data_view: nx.classes.reportviews.NodeDataView, node_id: NodeID
):
    node = nodes_data_view[str(node_id)]
    node["io_state"] = await compute_node_io_state(nodes_data_view, node_id)
    node["runnable_state"] = await compute_node_runnable_state(nodes_data_view, node_id)


def node_needs_computation(
    nodes_data_view: nx.classes.reportviews.NodeDataView, node_id: NodeID
) -> bool:
    node = nodes_data_view[str(node_id)]
    return (node.get("io_state", NodeIOState.OK) == NodeIOState.OUTDATED) or (
        node.get("runnable_state", NodeRunnableState.READY)
        == NodeRunnableState.WAITING_FOR_DEPENDENCIES
    )


@log_decorator(logger=logger)
async def _set_computational_nodes_states(complete_dag: nx.DiGraph) -> None:
    nodes_data_view: nx.classes.reportviews.NodeDataView = complete_dag.nodes.data()
    for node in nx.topological_sort(complete_dag):
        if _is_node_computational(nodes_data_view[node]["key"]):
            await compute_node_states(nodes_data_view, node)


@log_decorator(logger=logger)
async def create_minimal_computational_graph_based_on_selection(
    complete_dag: nx.DiGraph, selected_nodes: List[NodeID], force_restart: bool
) -> nx.DiGraph:
    nodes_data_view: nx.classes.reportviews.NodeDataView = complete_dag.nodes.data()

    try:
        # first pass, traversing in topological order to correctly get the dependencies, set the nodes states
        await _set_computational_nodes_states(complete_dag)
    except nx.NetworkXUnfeasible:
        # not acyclic, return an empty graph
        return nx.DiGraph()

    # second pass, detect all the nodes that need to be run
    minimal_nodes_selection: Set[NodeID] = set()
    if not selected_nodes:
        # fully automatic detection, we want anything that is waiting for dependencies or outdated
        minimal_nodes_selection.update(
            {
                n
                for n, _ in nodes_data_view
                if _is_node_computational(nodes_data_view[n]["key"])
                and (force_restart or node_needs_computation(nodes_data_view, n))
            }
        )
    else:
        # we want all the outdated nodes that are in the tree leading to the selected nodes
        for node in selected_nodes:
            minimal_nodes_selection.update(
                set(
                    n
                    for n in nx.bfs_tree(complete_dag, str(node), reverse=True)
                    if _is_node_computational(nodes_data_view[n]["key"])
                    and (force_restart or node_needs_computation(nodes_data_view, n))
                )
            )

    return complete_dag.subgraph(minimal_nodes_selection)


@log_decorator(logger=logger)
async def compute_pipeline_details(
    complete_dag: nx.DiGraph, pipeline_dag: nx.DiGraph
) -> PipelineDetails:

    # first pass, traversing in topological order to correctly get the dependencies, set the nodes states
    await _set_computational_nodes_states(complete_dag)
    return PipelineDetails(
        adjacency_list=nx.to_dict_of_lists(pipeline_dag),
        node_states={
            node_id: NodeState(
                io_state=node_data.get("io_state"),
                runnable_state=node_data.get("runnable_state"),
            )
            for node_id, node_data in complete_dag.nodes.data()
            if node_id in pipeline_dag.nodes
        },
    )


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
