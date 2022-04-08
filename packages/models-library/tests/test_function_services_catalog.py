# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access

from collections import defaultdict

import pytest
from models_library.function_services_catalog.api import (
    is_function_service,
    iter_service_docker_data,
)
from models_library.services import ServiceDockerData


@pytest.mark.parametrize(
    "image_metadata", iter_service_docker_data(), ids=lambda obj: obj.name
)
def test_create_frontend_services_metadata(image_metadata):
    assert isinstance(image_metadata, ServiceDockerData)

    assert is_function_service(image_metadata.key)


def test_catalog_frontend_services_registry():
    registry = {(s.key, s.version): s for s in iter_service_docker_data()}

    for s in registry.values():
        print(s.json(exclude_unset=True, indent=1))

    # one version per front-end service?
    versions_per_service = defaultdict(list)
    for s in registry.values():
        versions_per_service[s.key].append(s.version)

    assert not any(len(v) > 1 for v in versions_per_service.values())
