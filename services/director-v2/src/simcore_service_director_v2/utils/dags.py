import contextlib
import datetime
import logging
from copy import deepcopy
from typing import Any, cast

import arrow
import networkx as nx
from models_library.projects import NodesDict
from models_library.projects_nodes import NodeState
from models_library.projects_nodes_io import NodeID, NodeIDStr, PortLink
from models_library.projects_pipeline import PipelineDetails
from models_library.projects_state import RunningState
from models_library.utils.nodes import compute_node_hash

from ..models.comp_tasks import CompTaskAtDB
from ..modules.db.tables import NodeClass
from .computations import to_node_class

_logger = logging.getLogger(__name__)


kNODE_MODIFIED_STATE = "modified_state"
kNODE_DEPENDENCIES_TO_COMPUTE = "dependencies_state"


def create_complete_dag(workbench: NodesDict) -> nx.DiGraph:
    """creates a complete graph out of the project workbench"""
    dag_graph: nx.DiGraph = nx.DiGraph()
    for node_id, node in workbench.items():
        assert node.state  # nosec

        dag_graph.add_node(
            node_id,
            name=node.label,
            key=node.key,
            version=node.version,
            inputs=node.inputs,
            run_hash=node.run_hash,
            outputs=node.outputs,
            state=node.state.current_status,
            node_class=to_node_class(node.key),
        )
        if node.input_nodes:
            for input_node_id in node.input_nodes:
                predecessor_node = workbench.get(f"{input_node_id}")
                assert (  # nosec
                    predecessor_node
                ), f"Node {input_node_id} not found in workbench"
                if predecessor_node:
                    dag_graph.add_edge(str(input_node_id), node_id)

    return dag_graph


def create_complete_dag_from_tasks(tasks: list[CompTaskAtDB]) -> nx.DiGraph:
    dag_graph: nx.DiGraph = nx.DiGraph()
    for task in tasks:
        dag_graph.add_node(
            f"{task.node_id}",
            name=task.job_id,
            key=task.image.name,
            version=task.image.tag,
            inputs=task.inputs,
            run_hash=task.run_hash,
            outputs=task.outputs,
            state=task.state,
            node_class=task.node_class,
            progress=task.progress,
        )
        if task.inputs:
            for input_data in task.inputs.values():
                if isinstance(input_data, PortLink):
                    dag_graph.add_edge(str(input_data.node_uuid), f"{task.node_id}")
    return dag_graph


async def _compute_node_modified_state(
    graph_data: nx.classes.reportviews.NodeDataView, node_id: NodeID
) -> bool:
    node = graph_data[f"{node_id}"]
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
        result: dict[str, Any] = graph_data[f"{node_id}"]
        return result

    computed_hash = await compute_node_hash(node_id, get_node_io_payload_cb)
    return bool(computed_hash != node["run_hash"])


async def _compute_node_dependencies_state(graph_data, node_id) -> set[NodeID]:
    node = graph_data[f"{node_id}"]
    # check if the previous node is outdated or waits for dependencies... in which case this one has to wait
    non_computed_dependencies: set[NodeID] = set()
    for input_port in node.get("inputs", {}).values():
        if isinstance(input_port, PortLink) and _node_needs_computation(
            graph_data, input_port.node_uuid
        ):
            non_computed_dependencies.add(input_port.node_uuid)
    # all good. ready
    return non_computed_dependencies


async def _compute_node_states(
    graph_data: nx.classes.reportviews.NodeDataView, node_id: NodeID
) -> None:
    node = graph_data[f"{node_id}"]
    node[kNODE_MODIFIED_STATE] = await _compute_node_modified_state(graph_data, node_id)
    node[kNODE_DEPENDENCIES_TO_COMPUTE] = await _compute_node_dependencies_state(
        graph_data, node_id
    )


def _node_needs_computation(
    graph_data: nx.classes.reportviews.NodeDataView, node_id: NodeID
) -> bool:
    node = graph_data[f"{node_id}"]
    needs_computation: bool = node.get(kNODE_MODIFIED_STATE, False) or node.get(
        kNODE_DEPENDENCIES_TO_COMPUTE, None
    )
    return needs_computation


async def _set_computational_nodes_states(complete_dag: nx.DiGraph) -> None:
    graph_data: nx.classes.reportviews.NodeDataView = complete_dag.nodes.data()
    for node_id in nx.algorithms.dag.topological_sort(complete_dag):
        if graph_data[node_id]["node_class"] is NodeClass.COMPUTATIONAL:
            await _compute_node_states(graph_data, node_id)


async def create_minimal_computational_graph_based_on_selection(
    complete_dag: nx.DiGraph, selected_nodes: list[NodeID], force_restart: bool
) -> nx.DiGraph:
    graph_data: nx.classes.reportviews.NodeDataView = complete_dag.nodes.data()
    try:
        # first pass, traversing in topological order to correctly get the dependencies, set the nodes states
        await _set_computational_nodes_states(complete_dag)
    except nx.exception.NetworkXUnfeasible:
        # not acyclic, return an empty graph
        return nx.DiGraph()

    # second pass, detect all the nodes that need to be run
    minimal_nodes_selection: set[str] = set()
    if not selected_nodes:
        # fully automatic detection, we want anything that is waiting for dependencies or outdated
        minimal_nodes_selection.update(
            {
                n
                for n, _ in graph_data
                if graph_data[n]["node_class"] is NodeClass.COMPUTATIONAL
                and (force_restart or _node_needs_computation(graph_data, n))
            }
        )
    else:
        # we want all the outdated nodes that are in the tree leading to the selected nodes
        for node in selected_nodes:
            minimal_nodes_selection.update(
                {
                    n
                    for n in nx.bfs_tree(complete_dag, f"{node}", reverse=True)
                    if graph_data[n]["node_class"] is NodeClass.COMPUTATIONAL
                    and _node_needs_computation(graph_data, n)
                }
            )
            if (
                force_restart
                and graph_data[f"{node}"]["node_class"] is NodeClass.COMPUTATIONAL
            ):
                minimal_nodes_selection.add(f"{node}")

    return cast(nx.DiGraph, complete_dag.subgraph(minimal_nodes_selection))


def compute_pipeline_started_timestamp(
    pipeline_dag: nx.DiGraph, comp_tasks: list[CompTaskAtDB]
) -> datetime.datetime | None:
    if not pipeline_dag.nodes:
        return None
    node_id_to_comp_task: dict[NodeIDStr, CompTaskAtDB] = {
        f"{task.node_id}": task for task in comp_tasks
    }
    tomorrow = arrow.utcnow().shift(days=1).datetime
    pipeline_started_at: datetime.datetime | None = min(
        node_id_to_comp_task[node_id].start or tomorrow
        for node_id in pipeline_dag.nodes
    )
    if pipeline_started_at == tomorrow:
        pipeline_started_at = None
    return pipeline_started_at


def compute_pipeline_stopped_timestamp(
    pipeline_dag: nx.DiGraph, comp_tasks: list[CompTaskAtDB]
) -> datetime.datetime | None:
    if not pipeline_dag.nodes:
        return None
    node_id_to_comp_task: dict[NodeIDStr, CompTaskAtDB] = {
        f"{task.node_id}": task for task in comp_tasks
    }
    tomorrow = arrow.utcnow().shift(days=1).datetime
    pipeline_stopped_at: datetime.datetime | None = max(
        node_id_to_comp_task[node_id].end or tomorrow for node_id in pipeline_dag.nodes
    )
    if pipeline_stopped_at == tomorrow:
        pipeline_stopped_at = None
    return pipeline_stopped_at


async def compute_pipeline_details(
    complete_dag: nx.DiGraph, pipeline_dag: nx.DiGraph, comp_tasks: list[CompTaskAtDB]
) -> PipelineDetails:
    with contextlib.suppress(nx.exception.NetworkXUnfeasible):
        # NOTE: this problem of cyclic graphs for control loops create all kinds of issues that must be fixed
        # first pass, traversing in topological order to correctly get the dependencies, set the nodes states
        await _set_computational_nodes_states(complete_dag)

    # NOTE: the latest progress is available in comp_tasks only
    node_id_to_comp_task: dict[NodeIDStr, CompTaskAtDB] = {
        f"{task.node_id}": task for task in comp_tasks
    }
    pipeline_progress = None
    if len(pipeline_dag.nodes) > 0:
        pipeline_progress = sum(
            (node_id_to_comp_task[node_id].progress or 0) / len(pipeline_dag.nodes)
            for node_id in pipeline_dag.nodes
            if node_id in node_id_to_comp_task
            and node_id_to_comp_task[node_id].progress is not None
        )
        pipeline_progress = max(0.0, min(pipeline_progress, 1.0))

    return PipelineDetails(
        adjacency_list=nx.convert.to_dict_of_lists(pipeline_dag),
        progress=pipeline_progress,
        node_states={
            node_id: NodeState(
                modified=node_data.get(kNODE_MODIFIED_STATE, False),
                dependencies=node_data.get(kNODE_DEPENDENCIES_TO_COMPUTE, set()),
                current_status=(
                    node_id_to_comp_task[node_id].state
                    if node_id in node_id_to_comp_task
                    else RunningState.UNKNOWN
                ),
                progress=(
                    node_id_to_comp_task[node_id].progress
                    if node_id in node_id_to_comp_task
                    and node_id_to_comp_task[node_id].progress is not None
                    else None
                ),
            )
            for node_id, node_data in complete_dag.nodes.data()
            if node_data["node_class"] is NodeClass.COMPUTATIONAL
        },
    )


def find_computational_node_cycles(dag: nx.DiGraph) -> list[list[str]]:
    """returns a list of nodes part of a cycle and computational, which is currently forbidden."""

    list_potential_cycles = nx.algorithms.cycles.simple_cycles(dag)
    return [
        deepcopy(cycle)
        for cycle in list_potential_cycles
        if any(
            dag.nodes[node_id]["node_class"] is NodeClass.COMPUTATIONAL
            for node_id in cycle
        )
    ]
