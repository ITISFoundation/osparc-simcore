# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import itertools
import json
from typing import Any

import pytest
import simcore_service_invitations
import simcore_service_invitations.api._invitations
from pydantic import BaseModel
from pytest_simcore.pydantic_models import iter_model_examples_in_module


@pytest.mark.parametrize(
    "model_cls, example_name, example_data",
    itertools.chain(
        iter_model_examples_in_module(simcore_service_invitations.api._invitations),
        iter_model_examples_in_module(simcore_service_invitations.services.invitations),
    ),
)
def test_model_examples(
    model_cls: type[BaseModel], example_name: int, example_data: Any
):
    print(example_name, ":", json.dumps(example_data))
    assert model_cls.model_validate(example_data)
