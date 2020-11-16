# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access
# pylint:disable=no-value-for-parameter


import json
from pathlib import Path
from typing import Dict

import networkx as nx
import pytest
from models_library.project_nodes import Node
from models_library.projects import Workbench
from simcore_service_director_v2.utils.dags import create_dag_graph


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
