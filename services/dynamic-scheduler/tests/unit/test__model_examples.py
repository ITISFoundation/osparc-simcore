from typing import Any

import pytest
import simcore_service_dynamic_scheduler.models
from pydantic import BaseModel
from pytest_simcore.pydantic_models import (
    assert_validation_model,
    walk_model_examples_in_package,
)


@pytest.mark.parametrize(
    "model_cls, example_name, example_data",
    walk_model_examples_in_package(simcore_service_dynamic_scheduler.models),
)
def test_api_server_model_examples(
    model_cls: type[BaseModel], example_name: str, example_data: Any
):
    assert_validation_model(
        model_cls, example_name=example_name, example_data=example_data
    )
