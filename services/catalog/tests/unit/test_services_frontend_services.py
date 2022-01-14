# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access

import pytest
from simcore_service_catalog.models.schemas.services import (
    ServiceDockerData,
    ServiceOut,
)
from simcore_service_catalog.services.frontend_services import (
    is_frontend_service,
    iter_service_docker_data,
)


@pytest.mark.parametrize(
    "image_metadata", iter_service_docker_data(), ids=lambda obj: obj.name
)
def test_create_frontend_services_metadata(image_metadata: ServiceDockerData):
    assert isinstance(image_metadata, ServiceDockerData)

    assert is_frontend_service(image_metadata.key)

    assert ServiceOut.parse_obj(image_metadata.dict(by_alias=True))
