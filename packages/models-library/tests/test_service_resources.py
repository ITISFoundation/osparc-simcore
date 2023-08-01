# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from typing import Any

import pytest
from models_library.docker import DockerGenericTag
from models_library.services_resources import (
    ImageResources,
    ResourcesDict,
    ResourceValue,
    ServiceResourcesDict,
    ServiceResourcesDictHelpers,
)
from pydantic import parse_obj_as


@pytest.mark.parametrize(
    "example",
    (
        "simcore/services/dynamic/the:latest",
        "simcore/services/dynamic/nice-service:v1.0.0",
        "a/docker-hub/image:1.0.0",
        "traefik:v1.0.0",
        "traefik:v1.0.0@sha256:4bed291aa5efb9f0d77b76ff7d4ab71eee410962965d052552db1fb80576431d",
    ),
)
def test_compose_image(example: str) -> None:
    parse_obj_as(DockerGenericTag, example)


@pytest.fixture
def resources_dict() -> ResourcesDict:
    return parse_obj_as(
        ResourcesDict, ImageResources.Config.schema_extra["example"]["resources"]
    )


@pytest.fixture
def compose_image() -> DockerGenericTag:
    return parse_obj_as(DockerGenericTag, "image:latest")


def _ensure_resource_value_is_an_object(data: ResourcesDict) -> None:
    assert type(data) == dict
    print(data)
    for entry in data.values():
        entry: ResourceValue = entry
        assert entry.limit
        assert entry.reservation


def test_resources_dict_parsed_as_expected(resources_dict: ResourcesDict) -> None:
    _ensure_resource_value_is_an_object(resources_dict)


def test_image_resources_parsed_as_expected() -> None:
    result: ImageResources = ImageResources.parse_obj(
        ImageResources.Config.schema_extra["example"]
    )
    _ensure_resource_value_is_an_object(result.resources)
    assert type(result) == ImageResources

    result: ImageResources = parse_obj_as(
        ImageResources, ImageResources.Config.schema_extra["example"]
    )
    assert type(result) == ImageResources
    _ensure_resource_value_is_an_object(result.resources)


@pytest.mark.parametrize(
    "example", ServiceResourcesDictHelpers.Config.schema_extra["examples"]
)
def test_service_resource_parsed_as_expected(
    example: dict[DockerGenericTag, Any], compose_image: DockerGenericTag
) -> None:
    def _assert_service_resources_dict(
        service_resources_dict: ServiceResourcesDict,
    ) -> None:
        assert type(service_resources_dict) == dict

        print(service_resources_dict)
        for image_resources in service_resources_dict.values():
            _ensure_resource_value_is_an_object(image_resources.resources)

    service_resources_dict: ServiceResourcesDict = parse_obj_as(
        ServiceResourcesDict, example
    )
    _assert_service_resources_dict(service_resources_dict)

    for image_resources in example.values():
        service_resources_dict_from_single_service = (
            ServiceResourcesDictHelpers.create_from_single_service(
                image=compose_image,
                resources=ImageResources.parse_obj(image_resources).resources,
            )
        )
        _assert_service_resources_dict(service_resources_dict_from_single_service)


@pytest.mark.parametrize(
    "example", ServiceResourcesDictHelpers.Config.schema_extra["examples"]
)
def test_create_jsonable_dict(example: dict[DockerGenericTag, Any]) -> None:
    service_resources_dict: ServiceResourcesDict = parse_obj_as(
        ServiceResourcesDict, example
    )
    result = ServiceResourcesDictHelpers.create_jsonable(service_resources_dict)
    assert example == result
