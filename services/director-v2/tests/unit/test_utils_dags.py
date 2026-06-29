# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access
# pylint:disable=no-value-for-parameter


import datetime
from dataclasses import dataclass
from typing import Any, Final
from uuid import uuid4

import networkx as nx
import pytest
from models_library.projects import NodesDict
from models_library.projects_nodes import NodeState
from models_library.projects_nodes_io import NodeID
from models_library.projects_pipeline import PipelineDetails
from models_library.projects_state import RunningState
from simcore_postgres_database.models.comp_tasks import NodeClass
from simcore_service_director_v2.models.comp_tasks import (
    CompTaskAtDB,
    Image,
    NodeSchema,
)
from simcore_service_director_v2.utils.dags import (
    compute_pipeline_details,
    create_complete_dag,
    create_minimal_computational_graph_based_on_selection,
    find_computational_node_cycles,
)


def test_create_complete_dag_graph(
    fake_workbench: NodesDict,
    fake_workbench_complete_adjacency: dict[str, list[str]],
):
    dag_graph = create_complete_dag(fake_workbench)
    assert nx.is_directed_acyclic_graph(dag_graph)
    assert nx.to_dict_of_lists(dag_graph) == fake_workbench_complete_adjacency


@dataclass
class MinimalGraphTest:
    subgraph: list[NodeID]
    force_exp_dag: dict[str, list[str]]
    not_forced_exp_dag: dict[str, list[str]]


@pytest.mark.parametrize(
    "graph",
    [
        pytest.param(
            MinimalGraphTest(
                subgraph=[],
                force_exp_dag={
                    "3a710d8b-565c-5f46-870b-b45ebe195fc7": ["415fefd1-d08b-53c1-adb0-16bed3a687ef"],
                    "e1e2ea96-ce8f-5abc-8712-b8ed312a782c": ["6ede1209-b459-5735-91fc-761aa584808d"],
                    "415fefd1-d08b-53c1-adb0-16bed3a687ef": ["6ede1209-b459-5735-91fc-761aa584808d"],
                    "6ede1209-b459-5735-91fc-761aa584808d": [],
                },
                not_forced_exp_dag={
                    "e1e2ea96-ce8f-5abc-8712-b8ed312a782c": ["6ede1209-b459-5735-91fc-761aa584808d"],
                    "415fefd1-d08b-53c1-adb0-16bed3a687ef": ["6ede1209-b459-5735-91fc-761aa584808d"],
                    "6ede1209-b459-5735-91fc-761aa584808d": [],
                },
            ),
            id="no sub selection returns the full graph",
        ),
        pytest.param(
            MinimalGraphTest(
                subgraph=[
                    NodeID("8902d36c-bc65-5b0d-848f-88aed72d7849"),
                    NodeID("3a710d8b-565c-5f46-870b-b45ebe195fc7"),
                    NodeID("415fefd1-d08b-53c1-adb0-16bed3a687ef"),
                    NodeID("e1e2ea96-ce8f-5abc-8712-b8ed312a782c"),
                    NodeID("6ede1209-b459-5735-91fc-761aa584808d"),
                    NodeID("82d7a25c-18d4-44dc-a997-e5c9a745e7fd"),
                ],
                force_exp_dag={
                    "3a710d8b-565c-5f46-870b-b45ebe195fc7": ["415fefd1-d08b-53c1-adb0-16bed3a687ef"],
                    "e1e2ea96-ce8f-5abc-8712-b8ed312a782c": ["6ede1209-b459-5735-91fc-761aa584808d"],
                    "415fefd1-d08b-53c1-adb0-16bed3a687ef": ["6ede1209-b459-5735-91fc-761aa584808d"],
                    "6ede1209-b459-5735-91fc-761aa584808d": [],
                },
                not_forced_exp_dag={
                    "e1e2ea96-ce8f-5abc-8712-b8ed312a782c": ["6ede1209-b459-5735-91fc-761aa584808d"],
                    "415fefd1-d08b-53c1-adb0-16bed3a687ef": ["6ede1209-b459-5735-91fc-761aa584808d"],
                    "6ede1209-b459-5735-91fc-761aa584808d": [],
                },
            ),
            id="all nodes selected returns the full graph",
        ),
        pytest.param(
            MinimalGraphTest(
                subgraph=[
                    NodeID("8902d36c-bc65-5b0d-848f-88aed72d7849"),  # file-picker
                    NodeID("3a710d8b-565c-5f46-870b-b45ebe195fc7"),  # sleeper 1
                ],
                force_exp_dag={
                    "3a710d8b-565c-5f46-870b-b45ebe195fc7": [],
                },
                not_forced_exp_dag={},
            ),
            id="nodes 0 and 1",
        ),
        pytest.param(
            MinimalGraphTest(
                subgraph=[
                    NodeID("8902d36c-bc65-5b0d-848f-88aed72d7849"),  # file-picker
                    NodeID("415fefd1-d08b-53c1-adb0-16bed3a687ef"),  # sleeper 2
                ],
                force_exp_dag={
                    "415fefd1-d08b-53c1-adb0-16bed3a687ef": [],
                },
                not_forced_exp_dag={
                    "415fefd1-d08b-53c1-adb0-16bed3a687ef": [],
                },
            ),
            id="node 0 and 2",
        ),
        pytest.param(
            MinimalGraphTest(
                subgraph=[
                    NodeID("415fefd1-d08b-53c1-adb0-16bed3a687ef"),  # sleeper 2
                    NodeID("6ede1209-b459-5735-91fc-761aa584808d"),  # sleeper 4
                ],
                force_exp_dag={
                    "415fefd1-d08b-53c1-adb0-16bed3a687ef": ["6ede1209-b459-5735-91fc-761aa584808d"],
                    "e1e2ea96-ce8f-5abc-8712-b8ed312a782c": ["6ede1209-b459-5735-91fc-761aa584808d"],
                    "6ede1209-b459-5735-91fc-761aa584808d": [],
                },
                not_forced_exp_dag={
                    "415fefd1-d08b-53c1-adb0-16bed3a687ef": ["6ede1209-b459-5735-91fc-761aa584808d"],
                    "e1e2ea96-ce8f-5abc-8712-b8ed312a782c": ["6ede1209-b459-5735-91fc-761aa584808d"],
                    "6ede1209-b459-5735-91fc-761aa584808d": [],
                },
            ),
            id="node 2 and 4",
        ),
        pytest.param(
            MinimalGraphTest(
                subgraph=[
                    NodeID("3a710d8b-565c-5f46-870b-b45ebe195fc7"),  # sleeper 1
                    NodeID("6ede1209-b459-5735-91fc-761aa584808d"),  # sleeper 4
                ],
                force_exp_dag={
                    "3a710d8b-565c-5f46-870b-b45ebe195fc7": ["415fefd1-d08b-53c1-adb0-16bed3a687ef"],
                    "415fefd1-d08b-53c1-adb0-16bed3a687ef": ["6ede1209-b459-5735-91fc-761aa584808d"],
                    "e1e2ea96-ce8f-5abc-8712-b8ed312a782c": ["6ede1209-b459-5735-91fc-761aa584808d"],
                    "6ede1209-b459-5735-91fc-761aa584808d": [],
                },
                not_forced_exp_dag={
                    "415fefd1-d08b-53c1-adb0-16bed3a687ef": ["6ede1209-b459-5735-91fc-761aa584808d"],
                    "e1e2ea96-ce8f-5abc-8712-b8ed312a782c": ["6ede1209-b459-5735-91fc-761aa584808d"],
                    "6ede1209-b459-5735-91fc-761aa584808d": [],
                },
            ),
            id="node 1 and 4",
        ),
    ],
)
async def test_create_minimal_graph(fake_workbench: NodesDict, graph: MinimalGraphTest):
    """the workbench is made of file-picker and 4 sleepers. sleeper 1 has already run."""
    complete_dag: nx.DiGraph = create_complete_dag(fake_workbench)

    # everything is outdated in that case
    reduced_dag: nx.DiGraph = await create_minimal_computational_graph_based_on_selection(
        complete_dag, graph.subgraph, force_restart=True
    )
    assert nx.to_dict_of_lists(reduced_dag) == graph.force_exp_dag

    # only the outdated stuff shall be found here
    reduced_dag_with_auto_detect: nx.DiGraph = await create_minimal_computational_graph_based_on_selection(
        complete_dag, graph.subgraph, force_restart=False
    )
    assert nx.to_dict_of_lists(reduced_dag_with_auto_detect) == graph.not_forced_exp_dag


async def test_create_minimal_graph_with_dynamic_cycle_and_disconnected_comp_nodes():
    """Regression test: dynamic-only cycles must not prevent disconnected
    computational nodes from being detected as runnable.

    Scenario: 2 dynamic (interactive) nodes forming a cycle + 2 disconnected
    computational nodes that have never run (no outputs, no run_hash).
    """
    dag = nx.DiGraph()
    # Dynamic cycle: dyn_a <-> dyn_b
    dag.add_node(
        "dyn_a",
        name="jupyter-a",
        key="simcore/services/dynamic/jupyter-math",
        version="1.0.0",
        inputs={},
        run_hash=None,
        outputs={},
        state=RunningState.NOT_STARTED,
        node_class=NodeClass.INTERACTIVE,
    )
    dag.add_node(
        "dyn_b",
        name="jupyter-b",
        key="simcore/services/dynamic/jupyter-math",
        version="1.0.0",
        inputs={},
        run_hash=None,
        outputs={},
        state=RunningState.NOT_STARTED,
        node_class=NodeClass.INTERACTIVE,
    )
    dag.add_edge("dyn_a", "dyn_b")
    dag.add_edge("dyn_b", "dyn_a")

    # Two disconnected computational nodes (never ran)
    dag.add_node(
        "comp_1",
        name="sleeper-1",
        key="simcore/services/comp/sleeper",
        version="1.0.0",
        inputs={},
        run_hash=None,
        outputs={},
        state=RunningState.NOT_STARTED,
        node_class=NodeClass.COMPUTATIONAL,
    )
    dag.add_node(
        "comp_2",
        name="sleeper-2",
        key="simcore/services/comp/sleeper",
        version="1.0.0",
        inputs={},
        run_hash=None,
        outputs={},
        state=RunningState.NOT_STARTED,
        node_class=NodeClass.COMPUTATIONAL,
    )

    # Without fix this would return an empty graph (topological_sort fails on cycle)
    minimal = await create_minimal_computational_graph_based_on_selection(dag, selected_nodes=[], force_restart=False)
    assert set(minimal.nodes()) == {"comp_1", "comp_2"}

    # Force restart should also work
    minimal_forced = await create_minimal_computational_graph_based_on_selection(
        dag, selected_nodes=[], force_restart=True
    )
    assert set(minimal_forced.nodes()) == {"comp_1", "comp_2"}


async def test_create_minimal_graph_with_dynamic_cycle_feeding_comp_node():
    """Dynamic nodes in a cycle that feed into a computational node.

    The computational node should still be detected as runnable even though
    its upstream dynamic nodes form a cycle.
    """
    dag = nx.DiGraph()
    dag.add_node(
        "dyn_a",
        name="jupyter-a",
        key="simcore/services/dynamic/jupyter-math",
        version="1.0.0",
        inputs={},
        run_hash=None,
        outputs={"out_1": 42},
        state=RunningState.SUCCESS,
        node_class=NodeClass.INTERACTIVE,
    )
    dag.add_node(
        "dyn_b",
        name="jupyter-b",
        key="simcore/services/dynamic/jupyter-math",
        version="1.0.0",
        inputs={},
        run_hash=None,
        outputs={"out_1": 99},
        state=RunningState.SUCCESS,
        node_class=NodeClass.INTERACTIVE,
    )
    dag.add_edge("dyn_a", "dyn_b")
    dag.add_edge("dyn_b", "dyn_a")

    # Computational node that takes input from dyn_a
    dag.add_node(
        "comp_1",
        name="sleeper-1",
        key="simcore/services/comp/sleeper",
        version="1.0.0",
        inputs={},
        run_hash=None,
        outputs={},
        state=RunningState.NOT_STARTED,
        node_class=NodeClass.COMPUTATIONAL,
    )
    dag.add_edge("dyn_a", "comp_1")

    minimal = await create_minimal_computational_graph_based_on_selection(dag, selected_nodes=[], force_restart=False)
    assert set(minimal.nodes()) == {"comp_1"}


@pytest.mark.parametrize(
    "dag_adjacency, node_keys, exp_cycles",
    [
        pytest.param({}, {}, [], id="empty dag exp no cycles"),
        pytest.param(
            {"node_1": ["node_2", "node_3"], "node_2": ["node_3"], "node_3": []},
            {
                "node_1": {
                    "key": "simcore/services/comp/fake",
                    "node_class": NodeClass.COMPUTATIONAL,
                },
                "node_2": {
                    "key": "simcore/services/comp/fake",
                    "node_class": NodeClass.COMPUTATIONAL,
                },
                "node_3": {
                    "key": "simcore/services/comp/fake",
                    "node_class": NodeClass.COMPUTATIONAL,
                },
            },
            [],
            id="cycle less dag expect no cycle",
        ),
        pytest.param(
            {
                "node_1": ["node_2"],
                "node_2": ["node_3"],
                "node_3": ["node_1"],
            },
            {
                "node_1": {
                    "key": "simcore/services/comp/fake",
                    "node_class": NodeClass.COMPUTATIONAL,
                },
                "node_2": {
                    "key": "simcore/services/comp/fake",
                    "node_class": NodeClass.COMPUTATIONAL,
                },
                "node_3": {
                    "key": "simcore/services/comp/fake",
                    "node_class": NodeClass.COMPUTATIONAL,
                },
            },
            [["node_1", "node_2", "node_3"]],
            id="dag with 1 cycle",
        ),
        pytest.param(
            {
                "node_1": ["node_2"],
                "node_2": ["node_3", "node_1"],
                "node_3": ["node_1"],
            },
            {
                "node_1": {
                    "key": "simcore/services/comp/fake",
                    "node_class": NodeClass.COMPUTATIONAL,
                },
                "node_2": {
                    "key": "simcore/services/comp/fake",
                    "node_class": NodeClass.COMPUTATIONAL,
                },
                "node_3": {
                    "key": "simcore/services/comp/fake",
                    "node_class": NodeClass.COMPUTATIONAL,
                },
            },
            [["node_1", "node_2", "node_3"], ["node_1", "node_2"]],
            id="dag with 2 cycles",
        ),
        pytest.param(
            {
                "node_1": ["node_2"],
                "node_2": ["node_3"],
                "node_3": ["node_1"],
            },
            {
                "node_1": {
                    "key": "simcore/services/comp/fake",
                    "node_class": NodeClass.COMPUTATIONAL,
                },
                "node_2": {
                    "key": "simcore/services/comp/fake",
                    "node_class": NodeClass.COMPUTATIONAL,
                },
                "node_3": {
                    "key": "simcore/services/dynamic/fake",
                    "node_class": NodeClass.INTERACTIVE,
                },
            },
            [["node_1", "node_2", "node_3"]],
            id="dag with 1 cycle and 1 dynamic services should fail",
        ),
        pytest.param(
            {
                "node_1": ["node_2"],
                "node_2": ["node_3"],
                "node_3": ["node_1"],
            },
            {
                "node_1": {
                    "key": "simcore/services/dynamic/fake",
                    "node_class": NodeClass.INTERACTIVE,
                },
                "node_2": {
                    "key": "simcore/services/comp/fake",
                    "node_class": NodeClass.COMPUTATIONAL,
                },
                "node_3": {
                    "key": "simcore/services/dynamic/fake",
                    "node_class": NodeClass.INTERACTIVE,
                },
            },
            [["node_1", "node_2", "node_3"]],
            id="dag with 1 cycle and 2 dynamic services should fail",
        ),
        pytest.param(
            {
                "node_1": ["node_2"],
                "node_2": ["node_3"],
                "node_3": ["node_1"],
            },
            {
                "node_1": {
                    "key": "simcore/services/dynamic/fake",
                    "node_class": NodeClass.INTERACTIVE,
                },
                "node_2": {
                    "key": "simcore/services/dynamic/fake",
                    "node_class": NodeClass.INTERACTIVE,
                },
                "node_3": {
                    "key": "simcore/services/dynamic/fake",
                    "node_class": NodeClass.INTERACTIVE,
                },
            },
            [],
            id="dag with 1 cycle and 3 dynamic services should be ok",
        ),
    ],
)
def test_find_computational_node_cycles(
    dag_adjacency: dict[str, list[str]],
    node_keys: dict[str, dict[str, Any]],
    exp_cycles: list[list[str]],
):
    dag = nx.from_dict_of_lists(dag_adjacency, create_using=nx.DiGraph)
    # add node attributes
    for key, values in node_keys.items():
        for attr, attr_value in values.items():
            dag.nodes[key][attr] = attr_value
    list_of_cycles = find_computational_node_cycles(dag)
    assert len(list_of_cycles) == len(exp_cycles), "expected number of cycles not found"
    for cycle in list_of_cycles:
        assert sorted(cycle) in exp_cycles


@dataclass
class PipelineDetailsTestParams:
    complete_dag: nx.DiGraph
    pipeline_dag: nx.DiGraph
    comp_tasks: list[CompTaskAtDB]
    expected_pipeline_details: PipelineDetails


@pytest.fixture()
def pipeline_test_params(
    dag_adjacency: dict[str, list[str]],
    node_keys: dict[str, dict[str, Any]],
    list_comp_tasks: list[CompTaskAtDB],
    expected_pipeline_details_output: PipelineDetails,
) -> PipelineDetailsTestParams:
    # resolve the naming
    node_name_to_uuid_map = {}
    resolved_dag_adjacency: dict[str, list[str]] = {}
    for node_a, next_nodes in dag_adjacency.items():
        resolved_dag_adjacency[node_name_to_uuid_map.setdefault(node_a, f"{uuid4()}")] = [
            node_name_to_uuid_map.setdefault(n, f"{uuid4()}") for n in next_nodes
        ]

    # create the complete dag
    complete_dag = nx.from_dict_of_lists(resolved_dag_adjacency, create_using=nx.DiGraph)
    # add node attributes
    for non_resolved_key, values in node_keys.items():
        for attr, attr_value in values.items():
            complete_dag.nodes[node_name_to_uuid_map[non_resolved_key]][attr] = attr_value

    pipeline_dag = nx.from_dict_of_lists(resolved_dag_adjacency, create_using=nx.DiGraph)

    # resolve the comp_tasks
    resolved_list_comp_tasks = [
        c.model_copy(update={"node_id": node_name_to_uuid_map[c.node_id]}) for c in list_comp_tasks
    ]

    # resolved the expected output

    resolved_expected_pipeline_details = expected_pipeline_details_output.model_copy(
        update={
            "adjacency_list": {
                NodeID(node_name_to_uuid_map[node_a]): [NodeID(node_name_to_uuid_map[n]) for n in next_nodes]
                for node_a, next_nodes in expected_pipeline_details_output.adjacency_list.items()
            },
            "node_states": {
                NodeID(node_name_to_uuid_map[node]): state
                for node, state in expected_pipeline_details_output.node_states.items()
            },
        }
    )

    return PipelineDetailsTestParams(
        complete_dag=complete_dag,
        pipeline_dag=pipeline_dag,
        comp_tasks=resolved_list_comp_tasks,
        expected_pipeline_details=resolved_expected_pipeline_details,
    )


_MANY_NODES: Final[int] = 60


@pytest.mark.parametrize(
    "dag_adjacency, node_keys, list_comp_tasks, expected_pipeline_details_output",
    [
        pytest.param(
            {},
            {},
            [],
            PipelineDetails(adjacency_list={}, progress=None, node_states={}),
            id="empty dag",
        ),
        pytest.param(
            {f"node_{x}": [] for x in range(_MANY_NODES)},
            {
                f"node_{x}": {
                    "key": "simcore/services/comp/fake",
                    "node_class": NodeClass.COMPUTATIONAL,
                    "state": RunningState.NOT_STARTED,
                    "outputs": None,
                }
                for x in range(_MANY_NODES)
            },
            [
                CompTaskAtDB.model_construct(
                    project_id=uuid4(),
                    node_id=f"node_{x}",
                    schema=NodeSchema(inputs={}, outputs={}),
                    inputs=None,
                    image=Image(name="simcore/services/comp/fake", tag="1.3.4"),
                    state=RunningState.NOT_STARTED,
                    internal_id=3,
                    node_class=NodeClass.COMPUTATIONAL,
                    created=datetime.datetime.now(tz=datetime.UTC),
                    modified=datetime.datetime.now(tz=datetime.UTC),
                    last_heartbeat=None,
                    progress=1.00,
                )
                for x in range(_MANY_NODES)
            ],
            PipelineDetails.model_construct(
                adjacency_list={f"node_{x}": [] for x in range(_MANY_NODES)},
                progress=1.0,
                node_states={f"node_{x}": NodeState(modified=True, progress=1) for x in range(_MANY_NODES)},
            ),
            id="when summing many node progresses there are issues with floating point pipeline progress",
        ),
        pytest.param(
            {"node_1": ["node_2", "node_3"], "node_2": ["node_3"], "node_3": []},
            {
                "node_1": {
                    "key": "simcore/services/comp/fake",
                    "node_class": NodeClass.COMPUTATIONAL,
                    "state": RunningState.NOT_STARTED,
                    "outputs": None,
                },
                "node_2": {
                    "key": "simcore/services/comp/fake",
                    "node_class": NodeClass.COMPUTATIONAL,
                    "state": RunningState.NOT_STARTED,
                    "outputs": None,
                },
                "node_3": {
                    "key": "simcore/services/comp/fake",
                    "node_class": NodeClass.COMPUTATIONAL,
                    "state": RunningState.NOT_STARTED,
                    "outputs": None,
                },
            },
            [
                # NOTE: we use construct here to be able to use non uuid names to simplify test setup
                CompTaskAtDB.model_construct(
                    project_id=uuid4(),
                    node_id="node_1",
                    schema=NodeSchema(inputs={}, outputs={}),
                    inputs=None,
                    image=Image(name="simcore/services/comp/fake", tag="1.3.4"),
                    state=RunningState.NOT_STARTED,
                    internal_id=3,
                    node_class=NodeClass.COMPUTATIONAL,
                    created=datetime.datetime.now(tz=datetime.UTC),
                    modified=datetime.datetime.now(tz=datetime.UTC),
                    last_heartbeat=None,
                ),
                CompTaskAtDB.model_construct(
                    project_id=uuid4(),
                    node_id="node_2",
                    schema=NodeSchema(inputs={}, outputs={}),
                    inputs=None,
                    image=Image(name="simcore/services/comp/fake", tag="1.3.4"),
                    state=RunningState.NOT_STARTED,
                    internal_id=3,
                    node_class=NodeClass.COMPUTATIONAL,
                    created=datetime.datetime.now(tz=datetime.UTC),
                    modified=datetime.datetime.now(tz=datetime.UTC),
                    last_heartbeat=None,
                ),
                CompTaskAtDB.model_construct(
                    project_id=uuid4(),
                    node_id="node_3",
                    schema=NodeSchema(inputs={}, outputs={}),
                    inputs=None,
                    image=Image(name="simcore/services/comp/fake", tag="1.3.4"),
                    state=RunningState.NOT_STARTED,
                    internal_id=3,
                    node_class=NodeClass.COMPUTATIONAL,
                    created=datetime.datetime.now(tz=datetime.UTC),
                    modified=datetime.datetime.now(tz=datetime.UTC),
                    last_heartbeat=None,
                    progress=1.00,
                ),
            ],
            PipelineDetails.model_construct(
                adjacency_list={
                    "node_1": ["node_2", "node_3"],
                    "node_2": ["node_3"],
                    "node_3": [],
                },
                progress=0.3333333333333333,
                node_states={
                    "node_1": NodeState(modified=True, progress=None),
                    "node_2": NodeState(modified=True, progress=None),
                    "node_3": NodeState(modified=True, progress=1),
                },
            ),
            id="proper dag",
        ),
    ],
)
async def test_compute_pipeline_details(
    pipeline_test_params: PipelineDetailsTestParams,
):
    received_details = await compute_pipeline_details(
        pipeline_test_params.complete_dag,
        pipeline_test_params.pipeline_dag,
        pipeline_test_params.comp_tasks,
    )
    assert received_details.model_dump() == pipeline_test_params.expected_pipeline_details.model_dump()


@pytest.mark.parametrize(
    "dag_adjacency, node_keys, list_comp_tasks, expected_pipeline_details_output",
    [
        pytest.param(
            {"node_1": ["node_2", "node_3"], "node_2": ["node_3"], "node_3": []},
            {
                "node_1": {
                    "key": "simcore/services/comp/fake",
                    "node_class": NodeClass.COMPUTATIONAL,
                    "state": RunningState.NOT_STARTED,
                    "outputs": None,
                },
                "node_2": {
                    "key": "simcore/services/comp/fake",
                    "node_class": NodeClass.COMPUTATIONAL,
                    "state": RunningState.NOT_STARTED,
                    "outputs": None,
                },
                "node_3": {
                    "key": "simcore/services/comp/fake",
                    "node_class": NodeClass.COMPUTATIONAL,
                    "state": RunningState.NOT_STARTED,
                    "outputs": None,
                },
            },
            [
                # NOTE: we use construct here to be able to use non uuid names to simplify test setup
                CompTaskAtDB.model_construct(
                    project_id=uuid4(),
                    node_id="node_1",
                    schema=NodeSchema(inputs={}, outputs={}),
                    inputs=None,
                    image=Image(name="simcore/services/comp/fake", tag="1.3.4"),
                    state=RunningState.NOT_STARTED,
                    internal_id=2,
                    node_class=NodeClass.COMPUTATIONAL,
                    created=datetime.datetime.now(tz=datetime.UTC),
                    modified=datetime.datetime.now(tz=datetime.UTC),
                    last_heartbeat=None,
                ),
                CompTaskAtDB.model_construct(
                    project_id=uuid4(),
                    node_id="node_2",
                    schema=NodeSchema(inputs={}, outputs={}),
                    inputs=None,
                    image=Image(name="simcore/services/comp/fake", tag="1.3.4"),
                    state=RunningState.NOT_STARTED,
                    internal_id=3,
                    node_class=NodeClass.COMPUTATIONAL,
                    created=datetime.datetime.now(tz=datetime.UTC),
                    modified=datetime.datetime.now(tz=datetime.UTC),
                    last_heartbeat=None,
                ),
            ],
            PipelineDetails.model_construct(
                adjacency_list={
                    "node_1": ["node_2", "node_3"],
                    "node_2": ["node_3"],
                    "node_3": [],
                },
                progress=0.0,
                node_states={
                    "node_1": NodeState(modified=True, progress=None),
                    "node_2": NodeState(modified=True, progress=None),
                    "node_3": NodeState(
                        modified=True,
                        progress=None,
                        current_status=RunningState.UNKNOWN,
                    ),
                },
            ),
            id="dag with missing tasks (node 3 is missing, so it is not skipped in the pipeline details)",
        )
    ],
)
@pytest.mark.acceptance_test("For https://github.com/ITISFoundation/osparc-simcore/issues/8172")
async def test_compute_pipeline_details_with_missing_tasks(
    pipeline_test_params: PipelineDetailsTestParams,
):
    received_details = await compute_pipeline_details(
        pipeline_test_params.complete_dag,
        pipeline_test_params.pipeline_dag,
        pipeline_test_params.comp_tasks,
    )
    assert received_details.model_dump() == pipeline_test_params.expected_pipeline_details.model_dump()
