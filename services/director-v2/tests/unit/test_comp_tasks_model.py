# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from pprint import pformat
from typing import Any, Dict

import pytest
from pydantic.main import BaseModel
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
