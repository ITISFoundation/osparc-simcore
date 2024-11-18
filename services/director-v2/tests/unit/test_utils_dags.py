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
                    "3a710d8b-565c-5f46-870b-b45ebe195fc7": [
                        "415fefd1-d08b-53c1-adb0-16bed3a687ef"
                    ],
                    "e1e2ea96-ce8f-5abc-8712-b8ed312a782c": [
                        "6ede1209-b459-5735-91fc-761aa584808d"
                    ],
                    "415fefd1-d08b-53c1-adb0-16bed3a687ef": [
                        "6ede1209-b459-5735-91fc-761aa584808d"
                    ],
                    "6ede1209-b459-5735-91fc-761aa584808d": [],
                },
                not_forced_exp_dag={
                    "e1e2ea96-ce8f-5abc-8712-b8ed312a782c": [
                        "6ede1209-b459-5735-91fc-761aa584808d"
                    ],
                    "415fefd1-d08b-53c1-adb0-16bed3a687ef": [
                        "6ede1209-b459-5735-91fc-761aa584808d"
                    ],
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
                    "3a710d8b-565c-5f46-870b-b45ebe195fc7": [
                        "415fefd1-d08b-53c1-adb0-16bed3a687ef"
                    ],
                    "e1e2ea96-ce8f-5abc-8712-b8ed312a782c": [
                        "6ede1209-b459-5735-91fc-761aa584808d"
                    ],
                    "415fefd1-d08b-53c1-adb0-16bed3a687ef": [
                        "6ede1209-b459-5735-91fc-761aa584808d"
                    ],
                    "6ede1209-b459-5735-91fc-761aa584808d": [],
                },
                not_forced_exp_dag={
                    "e1e2ea96-ce8f-5abc-8712-b8ed312a782c": [
                        "6ede1209-b459-5735-91fc-761aa584808d"
                    ],
                    "415fefd1-d08b-53c1-adb0-16bed3a687ef": [
                        "6ede1209-b459-5735-91fc-761aa584808d"
                    ],
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
                    "415fefd1-d08b-53c1-adb0-16bed3a687ef": [
                        "6ede1209-b459-5735-91fc-761aa584808d"
                    ],
                    "e1e2ea96-ce8f-5abc-8712-b8ed312a782c": [
                        "6ede1209-b459-5735-91fc-761aa584808d"
                    ],
                    "6ede1209-b459-5735-91fc-761aa584808d": [],
                },
                not_forced_exp_dag={
                    "415fefd1-d08b-53c1-adb0-16bed3a687ef": [
                        "6ede1209-b459-5735-91fc-761aa584808d"
                    ],
                    "e1e2ea96-ce8f-5abc-8712-b8ed312a782c": [
                        "6ede1209-b459-5735-91fc-761aa584808d"
                    ],
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
                    "3a710d8b-565c-5f46-870b-b45ebe195fc7": [
                        "415fefd1-d08b-53c1-adb0-16bed3a687ef"
                    ],
                    "415fefd1-d08b-53c1-adb0-16bed3a687ef": [
                        "6ede1209-b459-5735-91fc-761aa584808d"
                    ],
                    "e1e2ea96-ce8f-5abc-8712-b8ed312a782c": [
                        "6ede1209-b459-5735-91fc-761aa584808d"
                    ],
                    "6ede1209-b459-5735-91fc-761aa584808d": [],
                },
                not_forced_exp_dag={
                    "415fefd1-d08b-53c1-adb0-16bed3a687ef": [
                        "6ede1209-b459-5735-91fc-761aa584808d"
                    ],
                    "e1e2ea96-ce8f-5abc-8712-b8ed312a782c": [
                        "6ede1209-b459-5735-91fc-761aa584808d"
                    ],
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
    reduced_dag: nx.DiGraph = (
        await create_minimal_computational_graph_based_on_selection(
            complete_dag, graph.subgraph, force_restart=True
        )
    )
    assert nx.to_dict_of_lists(reduced_dag) == graph.force_exp_dag

    # only the outdated stuff shall be found here
    reduced_dag_with_auto_detect: nx.DiGraph = (
        await create_minimal_computational_graph_based_on_selection(
            complete_dag, graph.subgraph, force_restart=False
        )
    )
    assert nx.to_dict_of_lists(reduced_dag_with_auto_detect) == graph.not_forced_exp_dag


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
    # check the inputs make sense
    assert len(set(dag_adjacency)) == len(node_keys) == len(list_comp_tasks)
    assert dag_adjacency.keys() == node_keys.keys()
    assert len(
        {t.node_id for t in list_comp_tasks}.intersection(node_keys.keys())
    ) == len(set(dag_adjacency))

    # resolve the naming
    node_name_to_uuid_map = {}
    resolved_dag_adjacency: dict[str, list[str]] = {}
    for node_a, next_nodes in dag_adjacency.items():
        resolved_dag_adjacency[
            node_name_to_uuid_map.setdefault(node_a, f"{uuid4()}")
        ] = [node_name_to_uuid_map.setdefault(n, f"{uuid4()}") for n in next_nodes]

    # create the complete dag
    complete_dag = nx.from_dict_of_lists(
        resolved_dag_adjacency, create_using=nx.DiGraph
    )
    # add node attributes
    for non_resolved_key, values in node_keys.items():
        for attr, attr_value in values.items():
            complete_dag.nodes[node_name_to_uuid_map[non_resolved_key]][
                attr
            ] = attr_value

    pipeline_dag = nx.from_dict_of_lists(
        resolved_dag_adjacency, create_using=nx.DiGraph
    )

    # resolve the comp_tasks
    resolved_list_comp_tasks = [
        c.model_copy(update={"node_id": node_name_to_uuid_map[c.node_id]})
        for c in list_comp_tasks
    ]

    # resolved the expected output

    resolved_expected_pipeline_details = expected_pipeline_details_output.model_copy(
        update={
            "adjacency_list": {
                NodeID(node_name_to_uuid_map[node_a]): [
                    NodeID(node_name_to_uuid_map[n]) for n in next_nodes
                ]
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
                    submit=datetime.datetime.now(tz=datetime.timezone.utc),
                    created=datetime.datetime.now(tz=datetime.timezone.utc),
                    modified=datetime.datetime.now(tz=datetime.timezone.utc),
                    last_heartbeat=None,
                    progress=1.00,
                )
                for x in range(_MANY_NODES)
            ],
            PipelineDetails.model_construct(
                adjacency_list={f"node_{x}": [] for x in range(_MANY_NODES)},
                progress=1.0,
                node_states={
                    f"node_{x}": NodeState(modified=True, progress=1)
                    for x in range(_MANY_NODES)
                },
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
                    submit=datetime.datetime.now(tz=datetime.timezone.utc),
                    created=datetime.datetime.now(tz=datetime.timezone.utc),
                    modified=datetime.datetime.now(tz=datetime.timezone.utc),
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
                    submit=datetime.datetime.now(tz=datetime.timezone.utc),
                    created=datetime.datetime.now(tz=datetime.timezone.utc),
                    modified=datetime.datetime.now(tz=datetime.timezone.utc),
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
                    submit=datetime.datetime.now(tz=datetime.timezone.utc),
                    created=datetime.datetime.now(tz=datetime.timezone.utc),
                    modified=datetime.datetime.now(tz=datetime.timezone.utc),
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
    assert (
        received_details.model_dump()
        == pipeline_test_params.expected_pipeline_details.model_dump()
    )
