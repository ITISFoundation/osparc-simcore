# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from pprint import pformat
from typing import Any

import pytest
from models_library.projects_state import RunningState
from pydantic.main import BaseModel
from simcore_service_director_v2.models.comp_runs import CompRunsAtDB


@pytest.mark.parametrize(
    "model_cls",
    (CompRunsAtDB,),
)
def test_computation_run_model_examples(
    model_cls: type[BaseModel], model_cls_examples: dict[str, dict[str, Any]]
):
    for name, example in model_cls_examples.items():
        print(name, ":", pformat(example))
        model_instance = model_cls(**example)
        assert model_instance, f"Failed with {name}"


@pytest.mark.parametrize(
    "model_cls",
    (CompRunsAtDB,),
)
def test_computation_run_model_with_run_result_value_field(
    model_cls: type[BaseModel], model_cls_examples: dict[str, dict[str, Any]]
):
    for name, example in model_cls_examples.items():
        example["result"] = RunningState.WAITING_FOR_RESOURCES.value
        print(name, ":", pformat(example))
        model_instance = model_cls(**example)
        assert model_instance, f"Failed with {name}"
