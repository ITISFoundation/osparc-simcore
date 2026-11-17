# pylint:disable=redefined-outer-name

"""Common fixtures for the CodSpeed benchmark suite

NOTE: these benchmarks are measured with `pytest-codspeed` in CPU-simulation mode.
Keep them CPU-bound, deterministic and free of I/O (no network, no database, no
filesystem) so that the measurements stay stable across runs.
"""

from collections.abc import Callable
from typing import Any

import pytest

_NUM_NODES: int = 25


@pytest.fixture(scope="session")
def make_project() -> Callable[[int], dict[str, Any]]:
    """Returns a factory of API-like project payloads with a given number of nodes"""

    def _factory(num_nodes: int = _NUM_NODES) -> dict[str, Any]:
        workbench: dict[str, Any] = {}
        for index in range(num_nodes):
            node_id = f"1e5d2b1e-0000-4000-8000-{index:012d}"
            previous_node_id = f"1e5d2b1e-0000-4000-8000-{index - 1:012d}"
            workbench[node_id] = {
                "key": "simcore/services/comp/itis/sleeper",
                "version": "2.1.4",
                "label": f"sleeper-{index}",
                "progress": 0,
                "inputs": (
                    {
                        "input_1": {
                            "nodeUuid": previous_node_id,
                            "output": "output_1",
                        },
                        "input_2": index,
                        "input_3": False,
                        "input_4": index * 0.5,
                    }
                    if index
                    else {"input_2": 2, "input_3": False, "input_4": 0.0}
                ),
                "inputsUnits": {},
                "inputNodes": [previous_node_id] if index else [],
                "outputs": {
                    "output_1": {
                        "store": 0,
                        "path": f"{index}/single_number.txt",
                        "eTag": "8c7d43c9d1a4b0b2e4e6b9b8b4a0d4a1",
                    },
                    "output_2": index,
                },
                "state": {
                    "modified": True,
                    "dependencies": [],
                    "currentStatus": "NOT_STARTED",
                    "progress": None,
                },
            }

        return {
            "uuid": "2b6b1e2a-0000-4000-8000-000000000001",
            "name": "Benchmark study",
            "description": "A project used to benchmark model validation",
            "prjOwner": "benchmark@osparc.io",
            "accessRights": {"1": {"read": True, "write": True, "delete": True}},
            "thumbnail": None,
            "creationDate": "2019-05-24T10:36:57.813Z",
            "lastChangeDate": "2019-05-24T10:36:57.813Z",
            "workbench": workbench,
            "type": "STANDARD",
            "templateType": None,
            "productName": "osparc",
            "tags": [1, 2, 3],
            "classifiers": ["some:id:to:a:classifier"],
            "quality": {},
            "dev": {},
            "ui": {
                "workbench": {
                    node_id: {"position": {"x": 10 * index, "y": 20 * index}} for index, node_id in enumerate(workbench)
                },
                "slideshow": {},
                "currentNodeId": next(iter(workbench), None),
            },
        }

    return _factory
