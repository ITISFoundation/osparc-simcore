# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from collections import defaultdict

import pytest
from models_library.function_services_catalog._registry import (
    FunctionServices,
    FunctionServiceSettings,
    catalog,
)
from models_library.function_services_catalog.api import (
    is_function_service,
    iter_service_docker_data,
)
from models_library.services import ServiceMetaDataPublished


@pytest.mark.parametrize(
    "image_metadata", iter_service_docker_data(), ids=lambda obj: obj.name
)
def test_create_frontend_services_metadata(image_metadata):
    assert isinstance(image_metadata, ServiceMetaDataPublished)

    assert is_function_service(image_metadata.key)


def test_catalog_frontend_services_registry():
    registry = {(s.key, s.version): s for s in iter_service_docker_data()}

    for s in registry.values():
        print(s.model_dump_json(exclude_unset=True, indent=1))

    # one version per front-end service?
    versions_per_service = defaultdict(list)
    for s in registry.values():
        versions_per_service[s.key].append(s.version)

    assert not any(len(v) > 1 for v in versions_per_service.values())


def test_catalog_registry(monkeypatch: pytest.MonkeyPatch):
    assert catalog._functions
    assert catalog.settings

    # with dev features
    with monkeypatch.context() as patch:
        patch.setenv("CATALOG_DEV_FEATURES_ENABLED", "1")
        patch.setenv("DIRECTOR_V2_DEV_FEATURES_ENABLED", "0")
        patch.setenv("WEBSERVER_DEV_FEATURES_ENABLED", "0")

        dev_catalog = FunctionServices(settings=FunctionServiceSettings())
        dev_catalog.extend(catalog)

        assert not dev_catalog._skip_dev()
        assert dev_catalog._functions == catalog._functions

    # without dev features
    with monkeypatch.context() as patch:
        patch.setenv("CATALOG_DEV_FEATURES_ENABLED", "0")
        patch.setenv("DIRECTOR_V2_DEV_FEATURES_ENABLED", "0")
        patch.setenv("WEBSERVER_DEV_FEATURES_ENABLED", "0")

        prod_catalog = FunctionServices(settings=FunctionServiceSettings())
        prod_catalog.extend(catalog)

        assert prod_catalog._skip_dev()
        assert prod_catalog._functions == catalog._functions

        prod_services = set(prod_catalog.iter_services_key_version())
        dev_services = set(dev_catalog.iter_services_key_version())

        assert len(prod_services) < len(dev_services)
        assert prod_services.issubset(dev_services)
