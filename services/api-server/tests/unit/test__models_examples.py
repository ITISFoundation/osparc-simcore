# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import itertools
import json
import pkgutil
from typing import Any

import pytest
import simcore_service_api_server.models.domain
from pydantic import BaseModel
from pytest_simcore.pydantic_models import iter_model_examples_in_module

assert simcore_service_api_server.models  # nosec


@pytest.mark.parametrize(
    "model_cls, example_name, example_data",
    itertools.chain(
        *(
            iter_model_examples_in_module(module)
            for module in pkgutil.walk_packages("simcore_service_api_server.models")
        )
    ),
)
def test_api_server_model_examples(
    model_cls: type[BaseModel], example_name: int, example_data: Any
):
    print(example_name, ":", json.dumps(example_data))
    assert model_cls.parse_obj(example_data)
