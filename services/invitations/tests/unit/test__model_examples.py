# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import json
from typing import Any

import pytest
import simcore_service_invitations
from pydantic import BaseModel
from pytest_simcore.pydantic_models import walk_model_examples_in_package


@pytest.mark.parametrize(
    "model_cls, example_name, example_data",
    walk_model_examples_in_package(simcore_service_invitations),
)
def test_all_models_library_models_config_examples(
    model_cls: type[BaseModel], example_name: int, example_data: Any
):
    assert model_cls.parse_obj(
        example_data
    ), f"Failed {example_name} : {json.dumps(example_data)}"
