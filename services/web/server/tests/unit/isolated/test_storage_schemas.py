# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import json
from typing import Any

import pytest
import simcore_service_webserver.storage.schemas
from pydantic import BaseModel
from pytest_simcore.pydantic_models import iter_model_examples_in_module


@pytest.mark.parametrize(
    "model_cls, example_name, example_data",
    iter_model_examples_in_module(simcore_service_webserver.storage.schemas),
)
def test_model_examples(
    model_cls: type[BaseModel], example_name: int, example_data: Any
):
    print(example_name, ":", json.dumps(example_data))
    assert model_cls.model_validate(example_data)
