# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import json
from typing import Any

import pytest
import simcore_service_director.models
from pydantic import BaseModel, ValidationError
from pytest_simcore.pydantic_models import walk_model_examples_in_package


@pytest.mark.parametrize(
    "model_cls, example_name, example_data",
    walk_model_examples_in_package(simcore_service_director.models),
)
def test_director_service_model_examples(
    model_cls: type[BaseModel], example_name: int, example_data: Any
):
    try:
        assert model_cls.model_validate(example_data) is not None
    except ValidationError as err:
        pytest.fail(
            f"\n{example_name}: {json.dumps(example_data, indent=1)}\nError: {err}"
        )
