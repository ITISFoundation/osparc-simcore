# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from copy import deepcopy
from pprint import pformat
from typing import Any
from uuid import UUID

import networkx as nx
import pytest
from models_library.projects_state import RunningState
from pydantic.main import BaseModel
from simcore_service_director_v2.models.comp_pipelines import CompPipelineAtDB


@pytest.mark.parametrize(
    "model_cls",
    (CompPipelineAtDB,),
)
def test_computation_pipeline_model_examples(
    model_cls: type[BaseModel], model_cls_examples: dict[str, dict[str, Any]]
):
    for name, example in model_cls_examples.items():
        print(name, ":", pformat(example))
        model_instance = model_cls(**example)
        assert model_instance, f"Failed with {name}"


@pytest.mark.parametrize(
    "model_cls",
    (CompPipelineAtDB,),
)
def test_computation_pipeline_model_with_running_state_value_field(
    model_cls: type[BaseModel], model_cls_examples: dict[str, dict[str, Any]]
):
    for name, example in model_cls_examples.items():
        example[
            "state"
        ] = RunningState.WAITING_FOR_RESOURCES.value  # this is a specific Runningstate
        print(name, ":", pformat(example))
        model_instance = model_cls(**example)
        assert model_instance, f"Failed with {name}"


@pytest.mark.parametrize(
    "model_cls",
    (CompPipelineAtDB,),
)
def test_computation_pipeline_model_with_uuids_in_dag_field(
    model_cls: type[BaseModel], model_cls_examples: dict[str, dict[str, Any]]
):
    for name, example in model_cls_examples.items():
        old_dag_list = deepcopy(example["dag_adjacency_list"])
        example["dag_adjacency_list"] = {
            UUID(key): [UUID(n) for n in value] for key, value in old_dag_list.items()
        }
        print(name, ":", pformat(example))
        model_instance = model_cls(**example)
        assert model_instance, f"Failed with {name}"


@pytest.mark.parametrize(
    "model_cls",
    (CompPipelineAtDB,),
)
def test_computation_pipeline_model_get_graph(
    model_cls: type[BaseModel], model_cls_examples: dict[str, dict[str, Any]]
):
    for name, example in model_cls_examples.items():
        print(name, ":", pformat(example))
        model_instance = model_cls(**example)
        assert model_instance, f"Failed with {name}"

        assert isinstance(model_instance, CompPipelineAtDB)
        dag_graph = model_instance.get_graph()
        assert isinstance(dag_graph, nx.DiGraph)
