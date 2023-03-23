import logging
from copy import deepcopy
from typing import Any

import networkx as nx
from models_library.projects import Workbench
from models_library.projects_nodes import NodeID, NodeState
from models_library.projects_nodes_io import PortLink
from models_library.projects_pipeline import PipelineDetails
from models_library.projects_state import RunningState
from models_library.utils.nodes import compute_node_hash
from simcore_service_director_v2.models.domains.comp_tasks import CompTaskAtDB

from .computations import NodeClass, to_node_class
from .logging_utils import log_decorator

logger = logging.getLogger(__name__)


def _is_node_computational(node_key: str) -> bool:
    try:
        return to_node_class(node_key) == NodeClass.COMPUTATIONAL
    except ValueError:
        return False


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
            state=node.state.current_status,
        )
        for input_node_id in node.input_nodes:
            predecessor_node = workbench.get(str(input_node_id))
            if predecessor_node:
                dag_graph.add_edge(str(input_node_id), node_id)

    return dag_graph


@log_decorator(logger=logger)
def create_complete_dag_from_tasks(tasks: list[CompTaskAtDB]) -> nx.DiGraph:
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
            state=task.state,
        )
        for input_data in task.inputs.values():
            if isinstance(input_data, PortLink):
                dag_graph.add_edge(str(input_data.node_uuid), str(task.node_id))
    return dag_graph


async def compute_node_modified_state(
    nodes_data_view: nx.classes.reportviews.NodeDataView, node_id: NodeID
) -> bool:
    node = nodes_data_view[str(node_id)]
    # if the node state is in the modified state already
    if node["state"] in [
        None,
        RunningState.ABORTED,
        RunningState.FAILED,
    ]:
        return True
    # if the node has no output it is outdated for sure
    if not node["outputs"]:
        return True
    for output_port in node["outputs"]:
        if output_port is None:
            return True

    # maybe our inputs changed? let's compute the node hash and compare with the saved one
    async def get_node_io_payload_cb(node_id: NodeID) -> dict[str, Any]:
        return nodes_data_view[str(node_id)]

    computed_hash = await compute_node_hash(node_id, get_node_io_payload_cb)
    if computed_hash != node["run_hash"]:
        return True
    return False


async def compute_node_dependencies_state(nodes_data_view, node_id) -> set[NodeID]:
    node = nodes_data_view[str(node_id)]
    # check if the previous node is outdated or waits for dependencies... in which case this one has to wait
    non_computed_dependencies: set[NodeID] = set()
    for input_port in node.get("inputs", {}).values():
        if isinstance(input_port, PortLink):
            if node_needs_computation(nodes_data_view, input_port.node_uuid):
                non_computed_dependencies.add(input_port.node_uuid)
    # all good. ready
    return non_computed_dependencies


kNODE_MODIFIED_STATE = "modified_state"
kNODE_DEPENDENCIES_TO_COMPUTE = "dependencies_state"


async def compute_node_states(
    nodes_data_view: nx.classes.reportviews.NodeDataView, node_id: NodeID
):
    node = nodes_data_view[str(node_id)]
    node[kNODE_MODIFIED_STATE] = await compute_node_modified_state(
        nodes_data_view, node_id
    )
    node[kNODE_DEPENDENCIES_TO_COMPUTE] = await compute_node_dependencies_state(
        nodes_data_view, node_id
    )


def node_needs_computation(
    nodes_data_view: nx.classes.reportviews.NodeDataView, node_id: NodeID
) -> bool:
    node = nodes_data_view[str(node_id)]
    return node.get(kNODE_MODIFIED_STATE, False) or node.get(
        kNODE_DEPENDENCIES_TO_COMPUTE, None
    )


@log_decorator(logger=logger)
async def _set_computational_nodes_states(complete_dag: nx.DiGraph) -> None:
    nodes_data_view: nx.classes.reportviews.NodeDataView = complete_dag.nodes.data()
    for node in nx.topological_sort(complete_dag):
        if _is_node_computational(nodes_data_view[node].get("key", "")):
            await compute_node_states(nodes_data_view, node)


@log_decorator(logger=logger)
async def create_minimal_computational_graph_based_on_selection(
    complete_dag: nx.DiGraph, selected_nodes: list[NodeID], force_restart: bool
) -> nx.DiGraph:
    nodes_data_view: nx.classes.reportviews.NodeDataView = complete_dag.nodes.data()
    try:
        # first pass, traversing in topological order to correctly get the dependencies, set the nodes states
        await _set_computational_nodes_states(complete_dag)
    except nx.NetworkXUnfeasible:
        # not acyclic, return an empty graph
        return nx.DiGraph()

    # second pass, detect all the nodes that need to be run
    minimal_nodes_selection: set[str] = set()
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
                {
                    n
                    for n in nx.bfs_tree(complete_dag, f"{node}", reverse=True)
                    if _is_node_computational(nodes_data_view[n]["key"])
                    and node_needs_computation(nodes_data_view, n)
                }
            )
            if force_restart and _is_node_computational(
                nodes_data_view[f"{node}"]["key"]
            ):
                minimal_nodes_selection.add(f"{node}")

    return complete_dag.subgraph(minimal_nodes_selection)


@log_decorator(logger=logger)
async def compute_pipeline_details(
    complete_dag: nx.DiGraph, pipeline_dag: nx.DiGraph, comp_tasks: list[CompTaskAtDB]
) -> PipelineDetails:
    try:
        # FIXME: this problem of cyclic graphs for control loops create all kinds of issues that must be fixed
        # first pass, traversing in topological order to correctly get the dependencies, set the nodes states
        await _set_computational_nodes_states(complete_dag)
    except nx.NetworkXUnfeasible:
        # not acyclic
        pass
    return PipelineDetails(
        adjacency_list=nx.to_dict_of_lists(pipeline_dag),
        node_states={
            node_id: NodeState(
                modified=node_data.get(kNODE_MODIFIED_STATE, False),
                dependencies=node_data.get(kNODE_DEPENDENCIES_TO_COMPUTE, set()),
                currentStatus=next(
                    (task.state for task in comp_tasks if str(task.node_id) == node_id),
                    RunningState.UNKNOWN,
                ),
            )
            for node_id, node_data in complete_dag.nodes.data()
            if _is_node_computational(node_data.get("key", ""))
        },
    )


def find_computational_node_cycles(dag: nx.DiGraph) -> list[list[str]]:
    """returns a list of nodes part of a cycle and computational, which is currently forbidden."""
    computational_node_cycles = []
    list_potential_cycles = nx.simple_cycles(dag)
    for cycle in list_potential_cycles:
        if any(_is_node_computational(dag.nodes[node_id]["key"]) for node_id in cycle):
            computational_node_cycles.append(deepcopy(cycle))
    return computational_node_cycles
