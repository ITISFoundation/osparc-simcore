# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


import asyncio
import json
import logging
import random
import sys
from collections.abc import Awaitable, Iterator
from io import BytesIO
from pathlib import Path
from typing import Any, Literal, Protocol, TypedDict

import pytest
import requests
from aiodocker import utils
from aiodocker.docker import Docker
from aiodocker.exceptions import DockerError
from simcore_service_director.core.settings import ApplicationSettings

_logger = logging.getLogger(__name__)


CURRENT_DIR = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent


class NodeRequirementsDict(TypedDict):
    CPU: float
    RAM: float


class ServiceExtrasDict(TypedDict):
    node_requirements: NodeRequirementsDict
    build_date: str
    vcs_ref: str
    vcs_url: str


class ServiceDescriptionDict(TypedDict):
    key: str
    version: str
    type: Literal["computational", "dynamic"]


class ServiceInRegistryInfoDict(TypedDict):
    service_description: ServiceDescriptionDict
    docker_labels: dict[str, Any]
    image_path: str
    internal_port: int | None
    entry_point: str
    service_extras: ServiceExtrasDict


def _create_service_description(
    service_type: Literal["computational", "dynamic"], name: str, tag: str
) -> ServiceDescriptionDict:
    service_desc = json.loads(
        (CURRENT_DIR / "dummy_service_description-v1.json").read_text()
    )

    if service_type == "computational":
        service_key_type = "comp"
    elif service_type == "dynamic":
        service_key_type = "dynamic"
    else:
        msg = f"Invalid {service_type=}"
        raise ValueError(msg)

    service_desc["key"] = f"simcore/services/{service_key_type}/{name}"
    service_desc["version"] = tag
    service_desc["type"] = service_type

    return service_desc


def _create_docker_labels(
    service_description: ServiceDescriptionDict, *, bad_json_format: bool
) -> dict[str, str]:
    docker_labels = {}
    for key, value in service_description.items():
        docker_labels[".".join(["io", "simcore", key])] = json.dumps({key: value})
        if bad_json_format:
            docker_labels[".".join(["io", "simcore", key])] = (
                "d32;'" + docker_labels[".".join(["io", "simcore", key])]
            )

    return docker_labels


async def _create_base_image(labels, tag) -> dict[str, Any]:
    dockerfile = """
FROM alpine
CMD while true; do sleep 10; done
    """
    f = BytesIO(dockerfile.encode("utf-8"))
    tar_obj = utils.mktar_from_dockerfile(f)

    # build docker base image
    docker = Docker()
    base_docker_image = await docker.images.build(
        fileobj=tar_obj, encoding="gzip", rm=True, labels=labels, tag=tag
    )
    await docker.close()
    return base_docker_image


async def _build_and_push_image(
    registry_url: str,
    service_type: Literal["computational", "dynamic"],
    name: str,
    tag: str,
    dependent_image=None,
    *,
    bad_json_format: bool = False,
    app_settings: ApplicationSettings,
) -> ServiceInRegistryInfoDict:

    # crate image
    service_description = _create_service_description(service_type, name, tag)
    docker_labels = _create_docker_labels(
        service_description, bad_json_format=bad_json_format
    )
    additional_docker_labels = [
        {
            "name": "constraints",
            "type": "string",
            "value": ["node.role==manager"],
        }
    ]

    internal_port = None
    entry_point = ""
    if service_type == "dynamic":
        internal_port = random.randint(1, 65535)  # noqa: S311
        additional_docker_labels.append(
            {
                "name": "ports",
                "type": "int",
                "value": internal_port,
            }
        )
        entry_point = "/test/entry_point"
        docker_labels["simcore.service.bootsettings"] = json.dumps(
            [
                {
                    "name": "entry_point",
                    "type": "string",
                    "value": entry_point,
                }
            ]
        )
    docker_labels["simcore.service.settings"] = json.dumps(additional_docker_labels)
    if bad_json_format:
        docker_labels["simcore.service.settings"] = (
            "'fjks" + docker_labels["simcore.service.settings"]
        )

    if dependent_image is not None:
        dependent_description = dependent_image["service_description"]
        dependency_docker_labels = [
            {
                "key": dependent_description["key"],
                "tag": dependent_description["version"],
            }
        ]
        docker_labels["simcore.service.dependencies"] = json.dumps(
            dependency_docker_labels
        )
        if bad_json_format:
            docker_labels["simcore.service.dependencies"] = (
                "'fjks" + docker_labels["simcore.service.dependencies"]
            )

    # create the typical org.label-schema labels
    service_extras = ServiceExtrasDict(
        node_requirements=NodeRequirementsDict(
            CPU=app_settings.DIRECTOR_DEFAULT_MAX_NANO_CPUS / 1e9,
            RAM=app_settings.DIRECTOR_DEFAULT_MAX_MEMORY,
        ),
        build_date="2020-08-19T15:36:27Z",
        vcs_ref="ca180ef1",
        vcs_url="git@github.com:ITISFoundation/osparc-simcore.git",
    )
    docker_labels["org.label-schema.build-date"] = service_extras["build_date"]
    docker_labels["org.label-schema.schema-version"] = "1.0"
    docker_labels["org.label-schema.vcs-ref"] = service_extras["vcs_ref"]
    docker_labels["org.label-schema.vcs-url"] = service_extras["vcs_url"]

    image_tag = registry_url + "/{key}:{version}".format(
        key=service_description["key"], version=tag
    )
    await _create_base_image(docker_labels, image_tag)

    # push image to registry
    try:
        docker = Docker()
        await docker.images.push(image_tag)
    finally:
        await docker.close()

    # remove image from host
    # docker.images.remove(image_tag)

    return ServiceInRegistryInfoDict(
        service_description=service_description,
        docker_labels=docker_labels,
        image_path=image_tag,
        internal_port=internal_port,
        entry_point=entry_point,
        service_extras=service_extras,
    )


def _clean_registry(registry_url: str, list_of_images: list[ServiceInRegistryInfoDict]):
    request_headers = {"accept": "application/vnd.docker.distribution.manifest.v2+json"}
    for image in list_of_images:
        service_description = image["service_description"]
        # get the image digest
        tag = service_description["version"]
        url = "http://{host}/v2/{name}/manifests/{tag}".format(
            host=registry_url, name=service_description["key"], tag=tag
        )
        response = requests.get(url, headers=request_headers, timeout=10)
        docker_content_digest = response.headers["Docker-Content-Digest"]
        # remove the image from the registry
        url = "http://{host}/v2/{name}/manifests/{digest}".format(
            host=registry_url,
            name=service_description["key"],
            digest=docker_content_digest,
        )
        response = requests.delete(url, headers=request_headers, timeout=5)


class PushServicesCallable(Protocol):
    async def __call__(
        self,
        *,
        number_of_computational_services: int,
        number_of_interactive_services: int,
        inter_dependent_services: bool = False,
        bad_json_format: bool = False,
        version="1.0.",
    ) -> list[ServiceInRegistryInfoDict]:
        ...


@pytest.fixture
def push_services(
    docker_registry: str, app_settings: ApplicationSettings
) -> Iterator[PushServicesCallable]:
    registry_url = docker_registry
    list_of_pushed_images_tags: list[ServiceInRegistryInfoDict] = []
    dependent_images = []

    async def _build_push_images_to_docker_registry(
        *,
        number_of_computational_services,
        number_of_interactive_services,
        inter_dependent_services=False,
        bad_json_format=False,
        version="1.0.",
    ) -> list[ServiceInRegistryInfoDict]:
        try:
            dependent_image = None
            if inter_dependent_services:
                dependent_image = await _build_and_push_image(
                    registry_url=registry_url,
                    service_type="computational",
                    name="dependency",
                    tag="10.52.999999",
                    dependent_image=None,
                    bad_json_format=bad_json_format,
                    app_settings=app_settings,
                )
                dependent_images.append(dependent_image)

            images_to_build: list[Awaitable] = [
                _build_and_push_image(
                    registry_url=registry_url,
                    service_type="computational",
                    name="test",
                    tag=f"{version}{image_index}",
                    dependent_image=dependent_image,
                    bad_json_format=bad_json_format,
                    app_settings=app_settings,
                )
                for image_index in range(number_of_computational_services)
            ]

            images_to_build.extend(
                [
                    _build_and_push_image(
                        registry_url=registry_url,
                        service_type="dynamic",
                        name="test",
                        tag=f"{version}{image_index}",
                        dependent_image=dependent_image,
                        bad_json_format=bad_json_format,
                        app_settings=app_settings,
                    )
                    for image_index in range(number_of_interactive_services)
                ]
            )

            results = await asyncio.gather(*images_to_build)
            list_of_pushed_images_tags.extend(results)

        except DockerError:
            _logger.exception("Docker API error while building and pushing images")
            raise

        return list_of_pushed_images_tags

    yield _build_push_images_to_docker_registry

    _logger.info("clean registry")
    _clean_registry(registry_url, list_of_pushed_images_tags)
    _clean_registry(registry_url, dependent_images)
