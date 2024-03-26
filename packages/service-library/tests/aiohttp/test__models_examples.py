import json
from typing import Any

import pytest
import servicelib.aiohttp
from pydantic import BaseModel
from pytest_simcore.pydantic_models import walk_model_examples_in_package


@pytest.mark.parametrize(
    "model_cls, example_name, example_data",
    walk_model_examples_in_package(servicelib.aiohttp),
)
def test_all_models_config_examples_in_servicelib_aiohttp_package(
    model_cls: type[BaseModel], example_name: int, example_data: Any
):
    assert model_cls.parse_obj(
        example_data
    ), f"Failed {example_name} : {json.dumps(example_data)}"
