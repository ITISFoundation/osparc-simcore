# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable
from typing import Any

import pytest
import simcore_service_api_server.models
from pydantic import BaseModel
from pytest_simcore.pydantic_models import (
    assert_validation_model,
    walk_model_examples_in_package,
)
from simcore_postgres_database.models.users import UserRole
from simcore_service_api_server.models.schemas.profiles import UserRoleEnum


@pytest.mark.parametrize(
    "model_cls, example_name, example_data",
    walk_model_examples_in_package(simcore_service_api_server.models),
)
def test_api_server_model_examples(
    model_cls: type[BaseModel], example_name: int, example_data: Any
):
    assert_validation_model(
        model_cls, example_name=example_name, example_data=example_data
    )


def test_enums_in_sync():
    # if this test fails, API needs to be updated
    assert {e.value for e in UserRole} == {e.value for e in UserRoleEnum}
