# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from typing import Any

import pytest
import simcore_service_catalog.models
from models_library.api_schemas_catalog.services import (
    ServiceListFilters,
)
from models_library.services_enums import ServiceType
from pydantic import BaseModel, TypeAdapter
from pytest_simcore.pydantic_models import (
    assert_validation_model,
    walk_model_examples_in_package,
)
from simcore_service_catalog.models.services_db import ServiceDBFilters


@pytest.mark.parametrize(
    "model_cls, example_name, example_data",
    walk_model_examples_in_package(simcore_service_catalog.models),
)
def test_catalog_service_model_examples(
    model_cls: type[BaseModel], example_name: str, example_data: Any
):
    assert_validation_model(
        model_cls, example_name=example_name, example_data=example_data
    )


@pytest.mark.parametrize(
    "filters",
    [
        pytest.param(
            None,
            id="no filters",
        ),
        pytest.param(
            ServiceListFilters(
                service_type=ServiceType.COMPUTATIONAL,
                service_key_pattern="*",
                version_display_pattern="*",
            ),
            id="all filters",
        ),
        pytest.param(
            ServiceListFilters(
                service_type=ServiceType.COMPUTATIONAL,
                service_key_pattern="*",
                version_display_pattern="*",
            ),
            id="all filters with regex",
        ),
    ],
)
def test_adapter_to_domain_model(
    filters: ServiceListFilters | None,
):

    TypeAdapter(ServiceDBFilters | None).validate_python(filters, from_attributes=True)
