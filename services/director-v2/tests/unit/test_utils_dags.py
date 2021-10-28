# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access
# pylint:disable=no-value-for-parameter


from typing import Any, Dict, List, Set

import networkx as nx
import pytest
from models_library.projects import Workbench
from simcore_service_director_v2.utils.dags import (
    create_complete_dag,
    create_minimal_computational_graph_based_on_selection,
    find_computational_node_cycles,
)


def test_create_complete_dag_graph(
    fake_workbench: Workbench,
    fake_workbench_complete_adjacency: Dict[str, List[str]],
):
    dag_graph = create_complete_dag(fake_workbench)
    assert nx.is_directed_acyclic_graph(dag_graph)
    assert nx.to_dict_of_lists(dag_graph) == fake_workbench_complete_adjacency


@pytest.mark.parametrize(
    "subgraph, force_exp_dag, not_forced_exp_dag",
    [
        pytest.param(
            [],
            {
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
            {
                "e1e2ea96-ce8f-5abc-8712-b8ed312a782c": [
                    "6ede1209-b459-5735-91fc-761aa584808d"
                ],
                "415fefd1-d08b-53c1-adb0-16bed3a687ef": [
                    "6ede1209-b459-5735-91fc-761aa584808d"
                ],
                "6ede1209-b459-5735-91fc-761aa584808d": [],
            },
            id="no sub selection returns the full graph",
        ),
        pytest.param(
            [
                "8902d36c-bc65-5b0d-848f-88aed72d7849",
                "3a710d8b-565c-5f46-870b-b45ebe195fc7",
                "415fefd1-d08b-53c1-adb0-16bed3a687ef",
                "e1e2ea96-ce8f-5abc-8712-b8ed312a782c",
                "6ede1209-b459-5735-91fc-761aa584808d",
                "82d7a25c-18d4-44dc-a997-e5c9a745e7fd",
            ],
            {
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
            {
                "e1e2ea96-ce8f-5abc-8712-b8ed312a782c": [
                    "6ede1209-b459-5735-91fc-761aa584808d"
                ],
                "415fefd1-d08b-53c1-adb0-16bed3a687ef": [
                    "6ede1209-b459-5735-91fc-761aa584808d"
                ],
                "6ede1209-b459-5735-91fc-761aa584808d": [],
            },
            id="all nodes selected returns the full graph",
        ),
        pytest.param(
            [
                "8902d36c-bc65-5b0d-848f-88aed72d7849",  # file-picker
                "3a710d8b-565c-5f46-870b-b45ebe195fc7",  # sleeper 1
            ],
            {
                "3a710d8b-565c-5f46-870b-b45ebe195fc7": [],
            },
            {},
            id="nodes 0 and 1",
        ),
        pytest.param(
            [
                "8902d36c-bc65-5b0d-848f-88aed72d7849",  # file-picker
                "415fefd1-d08b-53c1-adb0-16bed3a687ef",  # sleeper 2
            ],
            {
                "415fefd1-d08b-53c1-adb0-16bed3a687ef": [],
            },
            {
                "415fefd1-d08b-53c1-adb0-16bed3a687ef": [],
            },
            id="node 0 and 2",
        ),
        pytest.param(
            [
                "415fefd1-d08b-53c1-adb0-16bed3a687ef",  # sleeper 2
                "6ede1209-b459-5735-91fc-761aa584808d",  # sleeper 4
            ],
            {
                "415fefd1-d08b-53c1-adb0-16bed3a687ef": [
                    "6ede1209-b459-5735-91fc-761aa584808d"
                ],
                "e1e2ea96-ce8f-5abc-8712-b8ed312a782c": [
                    "6ede1209-b459-5735-91fc-761aa584808d"
                ],
                "6ede1209-b459-5735-91fc-761aa584808d": [],
            },
            {
                "415fefd1-d08b-53c1-adb0-16bed3a687ef": [
                    "6ede1209-b459-5735-91fc-761aa584808d"
                ],
                "e1e2ea96-ce8f-5abc-8712-b8ed312a782c": [
                    "6ede1209-b459-5735-91fc-761aa584808d"
                ],
                "6ede1209-b459-5735-91fc-761aa584808d": [],
            },
            id="node 2 and 4",
        ),
    ],
)
async def test_create_minimal_graph(
    loop,
    fake_workbench: Workbench,
    subgraph: Set[str],
    force_exp_dag: Dict[str, List[str]],
    not_forced_exp_dag: Dict[str, List[str]],
):
    complete_dag: nx.DiGraph = create_complete_dag(fake_workbench)

    # everything is outdated in that case
    reduced_dag: nx.DiGraph = (
        await create_minimal_computational_graph_based_on_selection(
            complete_dag, subgraph, force_restart=True
        )
    )
    assert nx.to_dict_of_lists(reduced_dag) == force_exp_dag

    # only the outdated stuff shall be found here
    reduced_dag_with_auto_detect: nx.DiGraph = (
        await create_minimal_computational_graph_based_on_selection(
            complete_dag, subgraph, force_restart=False
        )
    )
    assert nx.to_dict_of_lists(reduced_dag_with_auto_detect) == not_forced_exp_dag


@pytest.mark.parametrize(
    "dag_adjacency, node_keys, exp_cycles",
    [
        pytest.param({}, {}, [], id="empty dag exp no cycles"),
        pytest.param(
            {"node_1": ["node_2", "node_3"], "node_2": ["node_3"], "node_3": []},
            {
                "node_1": {"key": "simcore/services/comp/fake"},
                "node_2": {"key": "simcore/services/comp/fake"},
                "node_3": {"key": "simcore/services/comp/fake"},
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
                "node_1": {"key": "simcore/services/comp/fake"},
                "node_2": {"key": "simcore/services/comp/fake"},
                "node_3": {"key": "simcore/services/comp/fake"},
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
                "node_1": {"key": "simcore/services/comp/fake"},
                "node_2": {"key": "simcore/services/comp/fake"},
                "node_3": {"key": "simcore/services/comp/fake"},
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
                "node_1": {"key": "simcore/services/comp/fake"},
                "node_2": {"key": "simcore/services/comp/fake"},
                "node_3": {"key": "simcore/services/dynamic/fake"},
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
                "node_1": {"key": "simcore/services/dynamic/fake"},
                "node_2": {"key": "simcore/services/comp/fake"},
                "node_3": {"key": "simcore/services/dynamic/fake"},
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
                "node_1": {"key": "simcore/services/dynamic/fake"},
                "node_2": {"key": "simcore/services/dynamic/fake"},
                "node_3": {"key": "simcore/services/dynamic/fake"},
            },
            [],
            id="dag with 1 cycle and 3 dynamic services should be ok",
        ),
    ],
)
def test_find_computational_node_cycles(
    dag_adjacency: Dict[str, List[str]],
    node_keys: Dict[str, Dict[str, Any]],
    exp_cycles: List[List[str]],
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
