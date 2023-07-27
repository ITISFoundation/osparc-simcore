# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from pprint import pformat

import pytest
from models_library.projects_pipeline import ComputationTask
from pydantic import BaseModel


@pytest.mark.parametrize(
    "model_cls",
    (ComputationTask,),
)
def test_computation_task_model_examples(
    model_cls: type[BaseModel], model_cls_examples: dict[str, dict]
):
    for name, example in model_cls_examples.items():
        print(name, ":", pformat(example))
        model_instance = model_cls(**example)
        assert model_instance, f"Failed with {name}"
