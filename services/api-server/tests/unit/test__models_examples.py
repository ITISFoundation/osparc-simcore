# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable
import json
from typing import Any

import pytest
import simcore_service_api_server.models.domain
from pydantic import BaseModel
from pytest_simcore.pydantic_models import walk_model_examples_in_package

assert simcore_service_api_server.models  # nosec


@pytest.mark.parametrize(
    "model_cls, example_name, example_data",
    walk_model_examples_in_package(simcore_service_api_server.models),
)
def test_api_server_model_examples(
    model_cls: type[BaseModel], example_name: int, example_data: Any
):
    print(example_name, ":", json.dumps(example_data))
    assert model_cls.parse_obj(example_data)
    assert model_cls.parse_obj(example_data)
