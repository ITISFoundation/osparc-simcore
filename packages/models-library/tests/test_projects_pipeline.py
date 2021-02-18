# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from pprint import pformat

import pytest
from models_library.projects_pipeline import ComputationTask


@pytest.mark.parametrize(
    "model_cls",
    (ComputationTask,),
)
def test_computation_task_model_examples(model_cls, model_cls_examples):
    for name, example in model_cls_examples.items():
        print(name, ":", pformat(example))
        model_instance = model_cls(**example)
        assert model_instance, f"Failed with {name}"
