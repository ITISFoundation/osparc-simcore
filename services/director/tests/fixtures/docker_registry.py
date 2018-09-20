import json
import logging
import textwrap
from pathlib import Path

import docker
import pytest
from pytest_docker import docker_ip, docker_services  # pylint:disable=W0611

_logger = logging.getLogger(__name__)

def is_responsive(url):
    try:
        docker_client = docker.from_env()
        docker_client.login(registry=url, username="test")
    except docker.errors.APIError:
        _logger.exception("Error while loggin into the registry")
        return False
    return True

def _create_base_image(base_dir, labels):
    # create a basic dockerfile
    docker_file = base_dir / "Dockerfile"
    with docker_file.open("w") as file_pointer:        
        file_pointer.write(textwrap.dedent("""
            FROM scratch
            CMD ['echo']
        """
        ))
    assert docker_file.exists() == True
    # build docker base image
    docker_client = docker.from_env()
    base_docker_image = docker_client.images.build(path=str(base_dir), rm=True, labels=labels)
    return base_docker_image[0]

def _create_service_description(service_type, name, tag):
    dummy_description_path = Path(__file__).parent / "dummy_service_description.json"
    with dummy_description_path.open() as file_pt:
        description_dict = json.load(file_pt)

    if service_type == "computational":
        service_key_type = "comp"
    elif service_type == "dynamic":
        service_key_type = "dynamic"
    description_dict["key"] = "simcore/services/" + service_key_type + "/" + name
    description_dict["version"] = tag
    description_dict["type"] = service_type

    # SAN TODO: validate the schema here
    
    return description_dict

def _create_docker_labels(service_description):
    docker_labels = {}
    for key, value in service_description.items():
        docker_labels[".".join(["io", "simcore", key])] = json.dumps({key:value})
    return docker_labels

def _build_push_image(docker_dir, registry_url, service_type, name, tag):
    docker_client = docker.from_env()
    # crate image
    service_description = _create_service_description(service_type, name, tag)
    docker_labels = _create_docker_labels(service_description)
    if service_type == "dynamic":
        docker_labels["simcore.service.settings"] = json.dumps([{"name": "ports", "type": "int", "value": 8888}])
    image = _create_base_image(docker_dir, labels=docker_labels)
    # tag image
    image_tag = registry_url + "/{key}:{version}".format(**service_description)
    assert image.tag(image_tag) == True
    # push image to registry
    docker_client.images.push(image_tag)
    # remove image from host
    docker_client.images.remove(image_tag)
    return {
        "service_description":service_description,
        "docker_labels":docker_labels,
        "image_path":image_tag
        }

def _clean_registry(registry_url, list_of_images):
    import requests
    request_headers = {'accept': "application/vnd.docker.distribution.manifest.v2+json"}
    for image in list_of_images:
        service_description = image["service_description"]
        # get the image digest
        url = registry_url + "/v2/" + service_description["key"] + "/manifests/" + service_description["version"]
        response = requests.request("GET", url, headers=request_headers)
        print(response.headers)
        docker_content_digest = response.headers["Docker-Content-Digest"]
        # remove the image from the registry
        url = registry_url + "/v2/" + service_description["key"] + "/manifests/" + docker_content_digest
        response = requests.request("DELETE", url, headers=request_headers)

# pylint:disable=redefined-outer-name
@pytest.fixture(scope="session")
def docker_registry(docker_ip, docker_services): 
    host = docker_ip
    port = docker_services.port_for('registry', 5000)
    url = "{host}:{port}".format(host=host, port=port)
    # Wait until we can connect
    docker_services.wait_until_responsive(
        check=lambda: is_responsive(url),
        timeout=30.0,
        pause=1.0,
    )

    # test the registry
    try:
        docker_client = docker.from_env()
        # get the hello world example from docker hub
        hello_world_image = docker_client.images.pull("hello-world","latest")
        # login to private registry
        docker_client.login(registry=url, username="test")
        # tag the image
        repo = url + "/hello-world:dev"
        assert hello_world_image.tag(repo) == True
        # push the image to the private registry
        docker_client.images.push(repo)
        # wipe the images
        docker_client.images.remove(image="hello-world:latest")
        docker_client.images.remove(image=hello_world_image.id)
        # pull the image from the private registry
        private_image = docker_client.images.pull(repo)
        docker_client.images.remove(image=private_image.id)
    except docker.errors.APIError:
        _logger.exception("Unexpected docker API error")
        raise

    yield url
    print("teardown docker registry")

@pytest.fixture(scope="function")
def push_services(docker_registry, tmpdir):
    registry_url = docker_registry
    tmp_dir = Path(tmpdir)

    list_of_pushed_images_tags = []
    def build_push_images(number_of_computational_services, number_of_interactive_services):        
        try:        
            for image_index in range(0, number_of_computational_services):                
                image = _build_push_image(tmp_dir, registry_url, "computational", "test", str(image_index))
                list_of_pushed_images_tags.append(image)
            for image_index in range(0, number_of_interactive_services):                
                image = _build_push_image(tmp_dir, registry_url, "dynamic", "test", str(image_index))
                list_of_pushed_images_tags.append(image)
        except docker.errors.APIError:
            _logger.exception("Unexpected docker API error")
            raise

        return list_of_pushed_images_tags

    yield build_push_images
    print("clean registry")
    _clean_registry(registry_url, list_of_pushed_images_tags)
