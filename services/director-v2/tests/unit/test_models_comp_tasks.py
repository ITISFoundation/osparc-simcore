# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from typing import Any

import pytest
from models_library.projects_state import RunningState
from pydantic.main import BaseModel
from pytest_simcore.pydantic_models import (
    assert_validation_model,
    iter_model_examples_in_class,
)
from simcore_postgres_database.models.comp_pipeline import StateType
from simcore_service_director_v2.models.comp_tasks import CompTaskAtDB


@pytest.mark.parametrize(
    "model_cls, example_name, example_data",
    iter_model_examples_in_class(CompTaskAtDB),
)
def test_computation_task_model_examples(model_cls: type[BaseModel], example_name: str, example_data: dict[str, Any]):
    model_instance = assert_validation_model(model_cls, example_name=example_name, example_data=example_data)

    assert isinstance(model_instance, CompTaskAtDB)
    db_model = model_instance.to_db_model()

    assert isinstance(db_model, dict)
    assert StateType(db_model["state"])


@pytest.mark.parametrize(
    "model_cls, example_name, example_data",
    iter_model_examples_in_class(CompTaskAtDB),
)
def test_computation_task_model_with_running_state_value_field(
    model_cls: type[BaseModel], example_name: str, example_data: dict[str, Any]
):
    example_data["state"] = RunningState.WAITING_FOR_RESOURCES.value
    model_instance = model_cls(**example_data)
    assert model_instance, f"Failed with {example_name}"


@pytest.mark.parametrize(
    "model_cls, example_name, example_data",
    iter_model_examples_in_class(CompTaskAtDB),
)
def test_computation_task_model_with_wrong_default_value_field(
    model_cls: type[BaseModel], example_name: str, example_data: dict[str, Any]
):
    for output_schema in example_data.get("schema", {}).get("outputs", {}).values():
        output_schema["defaultValue"] = None

    model_instance = model_cls(**example_data)
    assert model_instance, f"Failed with {example_name}"
