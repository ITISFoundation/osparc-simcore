import json
from typing import Any

import pytest
import simcore_service_dynamic_scheduler.models
from pydantic import BaseModel, TypeAdapter, ValidationError
from pytest_simcore.pydantic_models import walk_model_examples_in_package


@pytest.mark.parametrize(
    "model_cls, example_name, example_data",
    walk_model_examples_in_package(simcore_service_dynamic_scheduler.models),
)
def test_api_server_model_examples(
    model_cls: type[BaseModel], example_name: int, example_data: Any
):
    try:
        assert TypeAdapter(model_cls).validate_python(example_data) is not None
    except ValidationError as err:
        pytest.fail(
            f"\n{example_name}: {json.dumps(example_data, indent=1)}\nError: {err}"
        )
