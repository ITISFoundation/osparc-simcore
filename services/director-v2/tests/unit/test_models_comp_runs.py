# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from pprint import pformat
from typing import Any

import pytest
from models_library.projects_state import RunningState
from pydantic.main import BaseModel
from pytest_simcore.pydantic_models import (
    assert_validation_model,
    iter_model_examples_in_class,
)
from simcore_service_director_v2.models.comp_runs import CompRunsAtDB


@pytest.mark.parametrize(
    "model_cls, example_name, example_data",
    iter_model_examples_in_class(CompRunsAtDB),
)
def test_computation_run_model_examples(
    model_cls: type[BaseModel], example_name: str, example_data: dict[str, Any]
):
    assert_validation_model(
        model_cls, example_name=example_name, example_data=example_data
    )


@pytest.mark.parametrize(
    "model_cls, example_name, example_data",
    iter_model_examples_in_class(CompRunsAtDB),
)
def test_computation_run_model_with_run_result_value_field(
    model_cls: type[BaseModel], example_name: str, example_data: dict[str, Any]
):
    example_data["result"] = RunningState.WAITING_FOR_RESOURCES.value
    print(example_name, ":", pformat(example_data))
    model_instance = model_cls(**example_data)
    assert model_instance, f"Failed with {example_name}"
