import json
from typing import Any

import models_library
import pytest
from pydantic.v1 import BaseModel
from pytest_simcore.pydantic_models import walk_model_examples_in_package


@pytest.mark.parametrize(
    "model_cls, example_name, example_data",
    walk_model_examples_in_package(models_library),
)
def test_all_models_library_models_config_examples(
    model_cls: type[BaseModel], example_name: int, example_data: Any
):
    assert model_cls.parse_obj(
        example_data
    ), f"Failed {example_name} : {json.dumps(example_data)}"
