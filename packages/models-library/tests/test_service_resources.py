# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from typing import Any

import pytest
from models_library.docker import DockerGenericTag
from models_library.services_resources import (
    SERVICE_RESOURCES_DICT_EXAMPLES,
    ImageResources,
    ResourcesDict,
    ServiceResourcesDict,
    create_service_resources_from_single_service,
    service_resources_adapter,
)
from pydantic import TypeAdapter


@pytest.mark.parametrize(
    "example",
    [
        "simcore/services/dynamic/the:latest",
        "simcore/services/dynamic/nice-service:v1.0.0",
        "a/docker-hub/image:1.0.0",
        "traefik:v1.0.0",
        "traefik:v1.0.0@sha256:4bed291aa5efb9f0d77b76ff7d4ab71eee410962965d052552db1fb80576431d",
    ],
)
def test_compose_image(example: str) -> None:
    TypeAdapter(DockerGenericTag).validate_python(example)


@pytest.fixture
def resources_dict() -> ResourcesDict:
    return TypeAdapter(ResourcesDict).validate_python(ImageResources.model_json_schema()["example"]["resources"])


@pytest.fixture
def compose_image() -> DockerGenericTag:
    return TypeAdapter(DockerGenericTag).validate_python("image:latest")


def _ensure_resource_value_is_an_object(data: ResourcesDict) -> None:
    assert isinstance(data, dict)
    print(data)
    for entry in data.values():
        assert entry.limit
        assert entry.reservation


def test_resources_dict_parsed_as_expected(resources_dict: ResourcesDict) -> None:
    _ensure_resource_value_is_an_object(resources_dict)


def test_image_resources_parsed_as_expected() -> None:
    result = ImageResources.model_validate(ImageResources.model_json_schema()["example"])
    _ensure_resource_value_is_an_object(result.resources)
    assert isinstance(result, ImageResources)

    result = TypeAdapter(ImageResources).validate_python(ImageResources.model_json_schema()["example"])
    assert isinstance(result, ImageResources)
    _ensure_resource_value_is_an_object(result.resources)


@pytest.mark.parametrize("example", SERVICE_RESOURCES_DICT_EXAMPLES)
def test_service_resource_parsed_as_expected(
    example: dict[DockerGenericTag, Any], compose_image: DockerGenericTag
) -> None:
    def _assert_service_resources_dict(
        service_resources_dict: ServiceResourcesDict,
    ) -> None:
        assert isinstance(service_resources_dict, dict)

        print(service_resources_dict)
        for image_resources in service_resources_dict.values():
            _ensure_resource_value_is_an_object(image_resources.resources)

    service_resources_dict = service_resources_adapter.validate_python(example)
    _assert_service_resources_dict(service_resources_dict)

    for image_resources in example.values():
        service_resources_dict_from_single_service = create_service_resources_from_single_service(
            image=compose_image,
            resources=ImageResources.model_validate(image_resources).resources,
        )
        _assert_service_resources_dict(service_resources_dict_from_single_service)


@pytest.mark.parametrize("example", SERVICE_RESOURCES_DICT_EXAMPLES)
def test_create_jsonable_dict(example: dict[DockerGenericTag, Any]) -> None:
    service_resources_dict = service_resources_adapter.validate_python(example)
    assert example == service_resources_adapter.dump_python(service_resources_dict, mode="json")
