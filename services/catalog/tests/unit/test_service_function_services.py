# pylint: disable=not-context-manager
# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import pytest
from models_library.api_schemas_catalog.services import ServiceMetaDataPublished
from simcore_service_catalog.service.function_services import (
    is_function_service,
    iter_service_docker_data,
)


@pytest.mark.parametrize(
    "image_metadata", iter_service_docker_data(), ids=lambda obj: obj.name
)
def test_create_services_metadata(image_metadata: ServiceMetaDataPublished):
    assert isinstance(image_metadata, ServiceMetaDataPublished)

    assert is_function_service(image_metadata.key)
