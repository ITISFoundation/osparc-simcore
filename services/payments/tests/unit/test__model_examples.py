# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import json
from typing import Any

import pytest
import simcore_service_payments.models
from models_library.basic_types import DECIMAL_PLACES
from pydantic import BaseModel, ValidationError
from pytest_simcore.pydantic_models import walk_model_examples_in_package
from simcore_postgres_database.constants import DECIMAL_PLACES as DECIMAL_PLACES_FROM_PG


@pytest.mark.parametrize(
    "model_cls, example_name, example_data",
    walk_model_examples_in_package(simcore_service_payments.models),
)
def test_api_server_model_examples(
    model_cls: type[BaseModel], example_name: int, example_data: Any
):
    try:
        assert model_cls.parse_obj(example_data) is not None
    except ValidationError as err:
        pytest.fail(
            f"\n{example_name}: {json.dumps(example_data, indent=1)}\nError: {err}"
        )


def test_postgres_and_models_library_same_decimal_places_constant():
    assert DECIMAL_PLACES == DECIMAL_PLACES_FROM_PG
