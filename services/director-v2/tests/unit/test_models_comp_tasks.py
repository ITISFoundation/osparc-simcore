# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from pprint import pformat
from typing import Any, Dict

import pytest
from models_library.projects_state import RunningState
from pydantic.main import BaseModel
from simcore_postgres_database.models.comp_pipeline import StateType
from simcore_service_director_v2.models.domains.comp_tasks import CompTaskAtDB


@pytest.mark.parametrize(
    "model_cls",
    (CompTaskAtDB,),
)
def test_computation_task_model_examples(
    model_cls: BaseModel, model_cls_examples: Dict[str, Dict[str, Any]]
):
    for name, example in model_cls_examples.items():
        print(name, ":", pformat(example))
        model_instance = model_cls(**example)
        assert model_instance, f"Failed with {name}"


@pytest.mark.parametrize(
    "model_cls",
    (CompTaskAtDB,),
)
def test_computation_task_model_export_to_db_model(
    model_cls: BaseModel, model_cls_examples: Dict[str, Dict[str, Any]]
):
    for name, example in model_cls_examples.items():
        print(name, ":", pformat(example))
        model_instance = model_cls(**example)
        assert model_instance, f"Failed with {name}"

        db_model = model_instance.to_db_model()
        assert isinstance(db_model, dict)
        StateType(db_model["state"])


@pytest.mark.parametrize(
    "model_cls",
    (CompTaskAtDB,),
)
def test_computation_task_model_with_running_state_value_field(
    model_cls: BaseModel, model_cls_examples: Dict[str, Dict[str, Any]]
):
    for name, example in model_cls_examples.items():
        example["state"] = RunningState.RETRY.value
        print(name, ":", pformat(example))
        model_instance = model_cls(**example)
        assert model_instance, f"Failed with {name}"


@pytest.mark.parametrize(
    "model_cls",
    (CompTaskAtDB,),
)
def test_computation_task_model_with_wrong_default_value_field(
    model_cls: BaseModel, model_cls_examples: Dict[str, Dict[str, Any]]
):
    for name, example in model_cls_examples.items():
        for output_schema in example.get("schema", {}).get("outputs", {}).values():
            output_schema["defaultValue"] = None

        print(name, ":", pformat(example))
        model_instance = model_cls(**example)
        assert model_instance, f"Failed with {name}"
