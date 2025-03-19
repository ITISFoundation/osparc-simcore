# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from typing import Any

import pytest
import simcore_service_webserver.storage.schemas
from pydantic import BaseModel
from pytest_simcore.pydantic_models import (
    assert_validation_model,
    iter_model_examples_in_module,
)


@pytest.mark.parametrize(
    "model_cls, example_name, example_data",
    iter_model_examples_in_module(simcore_service_webserver.storage.schemas),
)
def test_model_examples(
    model_cls: type[BaseModel], example_name: str, example_data: Any
):
    assert_validation_model(
        model_cls, example_name=example_name, example_data=example_data
    )
