import json
from typing import Any

import dask_task_models_library
import pytest
from pydantic import BaseModel
from pytest_simcore.pydantic_models import walk_model_examples_in_package


@pytest.mark.parametrize(
    "model_cls, example_name, example_data",
    walk_model_examples_in_package(dask_task_models_library),
)
def test_all_dask_task_models_library_models_config_examples(
    model_cls: type[BaseModel], example_name: str, example_data: Any
):
    assert model_cls.model_validate(example_data), f"Failed {example_name} : {json.dumps(example_data)}"
