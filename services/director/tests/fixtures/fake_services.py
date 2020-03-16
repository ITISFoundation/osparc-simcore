# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


import json
import logging
import random
from pathlib import Path

import docker
import pytest
import requests

_logger = logging.getLogger(__name__)


@pytest.fixture(scope="function")
def push_services(loop, docker_registry, tmpdir):
    registry_url = docker_registry
    tmp_dir = Path(tmpdir)

    list_of_pushed_images_tags = []
    dependent_images = []

    def build_push_images(
        number_of_computational_services,
        number_of_interactive_services,
        inter_dependent_services=False,
        bad_json_format=False,
        version="1.0.",
    ):
        try:
            dependent_image = None
            if inter_dependent_services:
                dependent_image = _build_push_image(
                    tmp_dir,
                    registry_url,
                    "computational",
                    "dependency",
                    "10.52.999999",
                    None,
                    bad_json_format=bad_json_format,
                )
                dependent_images.append(dependent_image)

            for image_index in range(0, number_of_computational_services):
                image = _build_push_image(
                    tmp_dir,
                    registry_url,
                    "computational",
                    "test",
                    version + str(image_index),
                    dependent_image,
                    bad_json_format=bad_json_format,
                )
                list_of_pushed_images_tags.append(image)

            for image_index in range(0, number_of_interactive_services):
                image = _build_push_image(
                    tmp_dir,
                    registry_url,
                    "dynamic",
                    "test",
                    version + str(image_index),
                    dependent_image,
                    bad_json_format=bad_json_format,
                )
                list_of_pushed_images_tags.append(image)
        except docker.errors.APIError:
            _logger.exception("Unexpected docker API error")
            raise

        return list_of_pushed_images_tags

    yield build_push_images
    _logger.info("clean registry")
    _clean_registry(registry_url, list_of_pushed_images_tags)
    _clean_registry(registry_url, dependent_images)


def _build_push_image(
    docker_dir,
    registry_url,
    service_type,
    name,
    tag,
    dependent_image=None,
    *,
    bad_json_format=False
):  # pylint: disable=R0913
    docker_client = docker.from_env()
    # crate image
    service_description = _create_service_description(service_type, name, tag)
    docker_labels = _create_docker_labels(service_description, bad_json_format)
    additional_docker_labels = [
        {"name": "constraints", "type": "string", "value": ["node.role==manager"]}
    ]
    internal_port = None
    entry_point = ""
    if service_type == "dynamic":
        internal_port = random.randint(1, 65535)
        additional_docker_labels.append(
            {"name": "ports", "type": "int", "value": internal_port}
        )
        entry_point = "/test/entry_point"
        docker_labels["simcore.service.bootsettings"] = json.dumps(
            [{"name": "entry_point", "type": "string", "value": entry_point}]
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

    image = _create_base_image(docker_dir, docker_labels)
    # tag image
    image_tag = registry_url + "/{key}:{version}".format(
        key=service_description["key"], version=tag
    )
    assert image.tag(image_tag) is True
    # push image to registry
    docker_client.images.push(image_tag)
    # remove image from host
    docker_client.images.remove(image_tag)
    return {
        "service_description": service_description,
        "docker_labels": docker_labels,
        "image_path": image_tag,
        "internal_port": internal_port,
        "entry_point": entry_point,
    }


def _clean_registry(registry_url, list_of_images):
    request_headers = {"accept": "application/vnd.docker.distribution.manifest.v2+json"}
    for image in list_of_images:
        service_description = image["service_description"]
        # get the image digest
        tag = service_description["version"]
        url = "http://{host}/v2/{name}/manifests/{tag}".format(
            host=registry_url, name=service_description["key"], tag=tag
        )
        response = requests.get(url, headers=request_headers)
        docker_content_digest = response.headers["Docker-Content-Digest"]
        # remove the image from the registry
        url = "http://{host}/v2/{name}/manifests/{digest}".format(
            host=registry_url,
            name=service_description["key"],
            digest=docker_content_digest,
        )
        response = requests.delete(url, headers=request_headers)


def _create_base_image(base_dir, labels):
    # create a basic dockerfile
    docker_file = base_dir / "Dockerfile"
    with docker_file.open("w") as file_pointer:
        file_pointer.write("FROM alpine\nCMD while true; do sleep 10; done\n")
    assert docker_file.exists() == True
    # build docker base image
    docker_client = docker.from_env()
    base_docker_image = docker_client.images.build(
        path=str(base_dir), rm=True, labels=labels
    )
    return base_docker_image[0]


def _create_service_description(service_type, name, tag):
    file_name = "dummy_service_description-v1.json"
    dummy_description_path = Path(__file__).parent / file_name
    with dummy_description_path.open() as file_pt:
        service_desc = json.load(file_pt)

    if service_type == "computational":
        service_key_type = "comp"
    elif service_type == "dynamic":
        service_key_type = "dynamic"
    service_desc["key"] = "simcore/services/" + service_key_type + "/" + name
    service_desc["version"] = tag
    service_desc["type"] = service_type

    return service_desc


def _create_docker_labels(service_description, bad_json_format):
    docker_labels = {}
    for key, value in service_description.items():
        docker_labels[".".join(["io", "simcore", key])] = json.dumps({key: value})
        if bad_json_format:
            docker_labels[".".join(["io", "simcore", key])] = (
                "d32;'" + docker_labels[".".join(["io", "simcore", key])]
            )
    return docker_labels
