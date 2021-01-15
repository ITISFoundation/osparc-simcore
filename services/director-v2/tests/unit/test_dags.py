# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access
# pylint:disable=no-value-for-parameter


import json
from pathlib import Path
from typing import Dict, Set

import networkx as nx
import pytest
from models_library.projects import Workbench
from models_library.projects_nodes import Node
from simcore_service_director_v2.utils.dags import (
    create_dag_graph,
    create_minimal_graph_based_on_selection,
)


@pytest.fixture(scope="session")
def workbench(sleepers_workbench: Dict) -> Workbench:
    workbench: Workbench = {}
    for node_key, node_values in sleepers_workbench.items():
        workbench[node_key] = Node.parse_obj(node_values)
    return workbench


@pytest.fixture(scope="session")
def sleepers_workbench_adjacency_file(mocks_dir: Path) -> Path:
    file_path = mocks_dir / "4sleepers_workbench_adjacency_list.json"
    assert file_path.exists()
    return file_path


@pytest.fixture(scope="session")
def sleepers_workbench_adjacency(sleepers_workbench_adjacency_file: Path) -> Dict:
    return json.loads(sleepers_workbench_adjacency_file.read_text())


def test_create_dags(workbench: Workbench, sleepers_workbench_adjacency: Dict):
    dag: nx.DiGraph = create_dag_graph(workbench)
    assert nx.to_dict_of_lists(dag) == sleepers_workbench_adjacency


@pytest.mark.parametrize(
    "subgraph, exp_dag",
    [
        pytest.param(
            {},
            {},
            id="no nodes",
        ),
        pytest.param(
            {
                "8902d36c-bc65-5b0d-848f-88aed72d7849",  # sleeper 0
                "3a710d8b-565c-5f46-870b-b45ebe195fc7",  # sleeper 1
            },
            {
                "8902d36c-bc65-5b0d-848f-88aed72d7849": [
                    "3a710d8b-565c-5f46-870b-b45ebe195fc7"
                ],
                "3a710d8b-565c-5f46-870b-b45ebe195fc7": [],
            },
            id="nodes 0 and 1",
        ),
        pytest.param(
            {
                "8902d36c-bc65-5b0d-848f-88aed72d7849",  # sleeper 0
                "415fefd1-d08b-53c1-adb0-16bed3a687ef",  # sleeper 2
            },
            {
                "8902d36c-bc65-5b0d-848f-88aed72d7849": [
                    "3a710d8b-565c-5f46-870b-b45ebe195fc7"
                ],
                "3a710d8b-565c-5f46-870b-b45ebe195fc7": [
                    "415fefd1-d08b-53c1-adb0-16bed3a687ef"
                ],
                "415fefd1-d08b-53c1-adb0-16bed3a687ef": [],
            },
            id="node 0 and 2",
        ),
        pytest.param(
            {
                "8902d36c-bc65-5b0d-848f-88aed72d7849",  # sleeper 0
                "415fefd1-d08b-53c1-adb0-16bed3a687ef",  # sleeper 2
                "6ede1209-b459-5735-91fc-761aa584808d",  # sleeper 4
            },
            {
                "8902d36c-bc65-5b0d-848f-88aed72d7849": [
                    "3a710d8b-565c-5f46-870b-b45ebe195fc7",
                    "e1e2ea96-ce8f-5abc-8712-b8ed312a782c",
                ],
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
            id="node 0, 2 and 4",
        ),
    ],
)
def test_create_minimal_graph(workbench: Workbench, subgraph: Set[str], exp_dag):
    full_dag_graph: nx.DiGraph = create_dag_graph(workbench)
    reduced_dag: nx.DiGraph = create_minimal_graph_based_on_selection(
        full_dag_graph, subgraph
    )
    assert nx.to_dict_of_lists(reduced_dag) == exp_dag
