# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access

import pytest
from models_library.api_schemas_catalog.services import ServiceDockerData
from simcore_service_catalog.services.function_services import (
    is_function_service,
    iter_service_docker_data,
)


@pytest.mark.parametrize(
    "image_metadata", iter_service_docker_data(), ids=lambda obj: obj.name
)
def test_create_services_metadata(image_metadata: ServiceDockerData):
    assert isinstance(image_metadata, ServiceDockerData)

    assert is_function_service(image_metadata.key)
