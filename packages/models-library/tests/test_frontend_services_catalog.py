# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access

import pytest
from models_library.frontend_services_catalog import (
    is_frontend_service,
    iter_service_docker_data,
)
from models_library.services import ServiceDockerData


@pytest.mark.parametrize(
    "image_metadata", iter_service_docker_data(), ids=lambda obj: obj.name
)
def test_create_frontend_services_metadata(image_metadata):
    assert isinstance(image_metadata, ServiceDockerData)

    assert is_frontend_service(image_metadata.key)
