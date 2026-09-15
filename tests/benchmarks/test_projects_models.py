"""Benchmarks for the validation/serialization of a project (aka study)

`Project` is the largest and most frequently (de)serialized model of the
platform: it is validated on every webserver request that touches a study and
dumped back to the front-end.
"""

from collections.abc import Callable
from typing import Any

import pytest
from common_library.json_serialization import json_dumps, json_loads
from models_library.projects import Project
from models_library.projects_nodes import Node

_SMALL_PROJECT_NUM_NODES = 1
_LARGE_PROJECT_NUM_NODES = 50


@pytest.fixture(scope="module")
def node_examples() -> list[dict[str, Any]]:
    examples = Node.model_json_schema(by_alias=True)["examples"]
    assert examples
    return examples


@pytest.mark.parametrize("num_nodes", [_SMALL_PROJECT_NUM_NODES, _LARGE_PROJECT_NUM_NODES])
def test_project_model_validate(benchmark, make_project: Callable[[int], dict[str, Any]], num_nodes: int):
    project_data = make_project(num_nodes)
    assert len(project_data["workbench"]) == num_nodes

    project = benchmark(Project.model_validate, project_data)
    assert project.uuid


def test_project_model_dump_by_alias(benchmark, make_project: Callable[[int], dict[str, Any]]):
    project = Project.model_validate(make_project(_LARGE_PROJECT_NUM_NODES))
    result = benchmark(lambda: project.model_dump(by_alias=True, exclude_unset=True))
    assert result["uuid"]


def test_project_model_dump_json(benchmark, make_project: Callable[[int], dict[str, Any]]):
    project = Project.model_validate(make_project(_LARGE_PROJECT_NUM_NODES))
    result = benchmark(lambda: project.model_dump_json(by_alias=True))
    assert result


def test_project_json_round_trip(benchmark, make_project: Callable[[int], dict[str, Any]]):
    """Full cycle: raw json text -> model -> json text (as done per API request)"""
    project_as_text = json_dumps(make_project(_LARGE_PROJECT_NUM_NODES))

    def _round_trip() -> str:
        project = Project.model_validate(json_loads(project_as_text))
        return json_dumps(project.model_dump(by_alias=True, mode="json"))

    assert benchmark(_round_trip)


def test_node_model_validate_examples(benchmark, node_examples: list[dict[str, Any]]):
    def _validate_all() -> list[Node]:
        return [Node.model_validate(example) for example in node_examples]

    assert len(benchmark(_validate_all)) == len(node_examples)
