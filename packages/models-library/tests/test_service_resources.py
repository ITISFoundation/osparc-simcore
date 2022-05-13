# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from pprint import pformat
from typing import Type

import pytest
from models_library.services_resources import (
    ComposeImage,
    ImageResources,
    ResourcesDict,
    ServiceResources,
)
from pydantic import BaseModel, parse_obj_as


@pytest.mark.parametrize(
    "model_cls",
    (
        ImageResources,
        ServiceResources,
    ),
)
def test_computation_task_model_examples(
    model_cls: Type[BaseModel], model_cls_examples: dict[str, dict]
):
    for name, example in model_cls_examples.items():
        print(name, ":", pformat(example))
        model_instance = model_cls.parse_obj(example)
        assert model_instance, f"Failed with {name}"


@pytest.mark.parametrize(
    "example",
    (
        "simcore/services/dynamic/the:latest",
        "simcore/services/dynamic/nice-service:v1.0.0",
        "a/docker-hub/image:1.0.0",
        "traefik:v1.0.0",
        "traefik:v1.0.0@somehash",
    ),
)
def test_compose_image(example: str) -> None:
    parse_obj_as(ComposeImage, example)


@pytest.fixture
def resources_dict() -> ResourcesDict:
    return ResourcesDict.parse_obj(
        ImageResources.Config.schema_extra["example"]["resources"]
    )


def test_service_resoruces_from_resources(resources_dict: ResourcesDict) -> None:
    image = "asdsad:asdsadsa"
    assert ServiceResources.from_resources(resources_dict, image)
