import json
from itertools import chain
from typing import Any

import pytest
import simcore_service_api_server.models.schemas
from pydantic import BaseModel
from pytest_simcore.pydantic_models import walk_model_examples_in_package


@pytest.mark.parametrize(
    "model_cls, example_name, example_data",
    chain(walk_model_examples_in_package(simcore_service_api_server.models)),
)
def test_all_models_library_models_config_examples(
    model_cls: type[BaseModel], example_name: int, example_data: Any
):
    assert model_cls.model_validate(
        example_data
    ), f"Failed {example_name} : {json.dumps(example_data)}"
