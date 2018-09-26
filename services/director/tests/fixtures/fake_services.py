from pathlib import Path
import logging
import docker
import pytest
import json

_logger = logging.getLogger(__name__)

@pytest.fixture(scope="function")
def push_services(docker_registry, tmpdir):
    registry_url = docker_registry
    tmp_dir = Path(tmpdir)

    list_of_pushed_images_tags = []
    def build_push_images(number_of_computational_services, number_of_interactive_services, sleep_time_s=60):
        try:        
            version = "1.0."
            for image_index in range(0, number_of_computational_services):                
                image = _build_push_image(tmp_dir, registry_url, "computational", "test", version + str(image_index), sleep_time_s)
                list_of_pushed_images_tags.append(image)
            for image_index in range(0, number_of_interactive_services):                
                image = _build_push_image(tmp_dir, registry_url, "dynamic", "test", version + str(image_index), sleep_time_s)
                list_of_pushed_images_tags.append(image)
        except docker.errors.APIError:
            _logger.exception("Unexpected docker API error")
            raise

        return list_of_pushed_images_tags

    yield build_push_images
    print("clean registry")
    _clean_registry(registry_url, list_of_pushed_images_tags)

@pytest.fixture(scope="function")
def push_v0_schema_services(docker_registry, tmpdir):
    registry_url = docker_registry
    tmp_dir = Path(tmpdir)

    schema_version = "v0"
    list_of_pushed_images_tags = []
    def build_push_images(number_of_computational_services, number_of_interactive_services, sleep_time_s=10):        
        try:        
            version = "0.0."
            for image_index in range(0, number_of_computational_services):                
                image = _build_push_image(tmp_dir, registry_url, "computational", "test", version + str(image_index), sleep_time_s, schema_version)
                list_of_pushed_images_tags.append(image)
            for image_index in range(0, number_of_interactive_services):                
                image = _build_push_image(tmp_dir, registry_url, "dynamic", "test", version + str(image_index), sleep_time_s, schema_version)
                list_of_pushed_images_tags.append(image)
        except docker.errors.APIError:
            _logger.exception("Unexpected docker API error")
            raise

        return list_of_pushed_images_tags

    yield build_push_images
    print("clean registry")
    _clean_registry(registry_url, list_of_pushed_images_tags, schema_version)

def _build_push_image(docker_dir, registry_url, service_type, name, tag, sleep_time_s, schema_version="v1"): # pylint: disable=R0913
    docker_client = docker.from_env()
    # crate image
    service_description = _create_service_description(service_type, name, tag, schema_version)
    docker_labels = _create_docker_labels(service_description)
    additional_docker_labels = [{"name": "constraints", "type": "string", "value": ["node.role==manager"]}]
    if service_type == "dynamic":
        additional_docker_labels.append({"name": "ports", "type": "int", "value": 8888})
    docker_labels["simcore.service.settings"] = json.dumps(additional_docker_labels)
    image = _create_base_image(docker_dir, docker_labels, sleep_time_s)
    # tag image
    image_tag = registry_url + "/{key}:{version}".format(key=service_description["key"], version=tag)
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

def _clean_registry(registry_url, list_of_images, schema_version="v1"):
    import requests
    request_headers = {'accept': "application/vnd.docker.distribution.manifest.v2+json"}
    for image in list_of_images:
        service_description = image["service_description"]
        # get the image digest
        if schema_version == "v0":
            tag = service_description["tag"]
        else:
            tag = service_description["version"]
        url = "http://{host}/v2/{name}/manifests/{tag}".format(host=registry_url, name=service_description["key"], tag=tag)
        response = requests.request("GET", url, headers=request_headers)        
        docker_content_digest = response.headers["Docker-Content-Digest"]
        # remove the image from the registry
        url = "http://{host}/v2/{name}/manifests/{digest}".format(host=registry_url, name=service_description["key"], digest=docker_content_digest)
        response = requests.request("DELETE", url, headers=request_headers)

def _create_base_image(base_dir, labels, sleep_time_s):
    # create a basic dockerfile
    docker_file = base_dir / "Dockerfile"
    with docker_file.open("w") as file_pointer:        
        file_pointer.write('FROM alpine\nCMD sleep %s\n' % (sleep_time_s))
    assert docker_file.exists() == True
    # build docker base image
    docker_client = docker.from_env()
    base_docker_image = docker_client.images.build(path=str(base_dir), rm=True, labels=labels)
    return base_docker_image[0]

def _create_service_description(service_type, name, tag, schema_version):
    file_name = "dummy_service_description-" + schema_version + ".json"
    dummy_description_path = Path(__file__).parent / file_name
    with dummy_description_path.open() as file_pt:
        service_desc = json.load(file_pt)

    if service_type == "computational":
        service_key_type = "comp"
    elif service_type == "dynamic":
        service_key_type = "dynamic"
    service_desc["key"] = "simcore/services/" + service_key_type + "/" + name    
    # version 0 had no validation, no version, no type
    if schema_version == "v0":
        service_desc["tag"] = tag
    elif schema_version == "v1":
        service_desc["version"] = tag
        service_desc["type"] = service_type        
    else:
        raise Exception("invalid version!!")

    return service_desc

def _create_docker_labels(service_description):
    docker_labels = {}
    for key, value in service_description.items():
        docker_labels[".".join(["io", "simcore", key])] = json.dumps({key:value})
    return docker_labels
