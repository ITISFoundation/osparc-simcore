# pylint:disable=wildcard-import
# pylint:disable=unused-import
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import os
import socket
from copy import deepcopy
from pathlib import Path
from typing import Dict

import pytest
import yaml


@pytest.fixture("session")
def services_docker_compose(osparc_simcore_root_dir) -> Dict[str, str]:
    docker_compose_path = osparc_simcore_root_dir / "services" / "docker-compose.yml"
    assert docker_compose_path.exists()

    content = {}
    with docker_compose_path.open() as f:
        content = yaml.safe_load(f)
    return content

@pytest.fixture("session")
def tools_docker_compose(osparc_simcore_root_dir) -> Dict[str, str]:
    docker_compose_path = osparc_simcore_root_dir / "services" / "docker-compose.tools.yml"
    assert docker_compose_path.exists()

    content = {}
    with docker_compose_path.open() as f:
        content = yaml.safe_load(f)
    return content

@pytest.fixture("session")
def image_environ():
    docker_registry = os.environ.get("DOCKER_REGISTRY")
    if docker_registry:
        if not str(docker_registry).endswith("/"):
            docker_registry = docker_registry + "/"
            os.environ["DOCKER_REGISTRY"] = docker_registry
    docker_image_tag = os.environ.get("DOCKER_IMAGE_TAG")
    if not docker_image_tag:
        os.environ["DOCKER_IMAGE_TAG"] = "latest"

@pytest.fixture("session")
def devel_environ(env_devel_file, image_environ) -> Dict[str, str]:
    """ Environ dict from .env-devel """
    env_devel = {}
    with env_devel_file.open() as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                key, value = line.split("=")
                env_devel[key] = str(value)
    # change some of the environ to accomodate the test case
    if 'REGISTRY_SSL' in env_devel:
        env_devel['REGISTRY_SSL'] = 'False'
    if 'REGISTRY_URL' in env_devel:
        env_devel['REGISTRY_URL'] = "{}:5000".format(_get_ip())
    if 'REGISTRY_USER' in env_devel:
        env_devel['REGISTRY_USER'] = "simcore"
    if 'REGISTRY_PW' in env_devel:
        env_devel['REGISTRY_PW'] = ""
    if 'REGISTRY_AUTH' in env_devel:
        env_devel['REGISTRY_AUTH'] = False
    return env_devel

@pytest.fixture(scope="module")
def temp_folder(request, tmpdir_factory) -> Path:
    tmp = Path(tmpdir_factory.mktemp("docker_compose_{}".format(request.module.__name__)))
    yield tmp

@pytest.fixture(scope='module')
def docker_compose_file(request, temp_folder, services_docker_compose, devel_environ):
    """ Overrides pytest-docker fixture

    """
    core_services = getattr(request.module, 'core_services', []) # TODO: PC->SAN could also be defined as a fixture (as with docker_compose)
    docker_compose_path = temp_folder / 'docker-compose.yml'

    _recreate_compose_file(core_services, services_docker_compose, docker_compose_path, devel_environ)
    yield Path(docker_compose_path)

    # cleanup
    # docker_compose_path.unlink()

@pytest.fixture(scope='module')
def tools_docker_compose_file(request, temp_folder, tools_docker_compose, devel_environ):
    """ Overrides pytest-docker fixture

    """
    tool_services = getattr(request.module, 'tool_services', [])
    docker_compose_path = temp_folder / 'docker-compose.tools.yml'
    # docker_compose_path = tmp_path / 'docker-compose.tools.yml'
    _recreate_compose_file(tool_services, tools_docker_compose, docker_compose_path, devel_environ)

    yield Path(docker_compose_path)

    # cleanup
    # Path(docker_compose_path).unlink()

# HELPERS ---------------------------------------------
def _get_ip()->str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't even have to be reachable
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception: #pylint: disable=W0703
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

def _recreate_compose_file(keep, services_compose, docker_compose_path, devel_environ):
    # reads service/docker-compose.yml
    content = deepcopy(services_compose)

    # remove unnecessary services
    remove = [name for name in content['services'] if name not in keep]
    for name in remove:
        content['services'].pop(name, None)

    for name in keep:
        service = content['services'][name]
        # remove builds
        if "build" in service:
            service.pop("build", None)
        # replaces environs
        if "environment" in service:
            _environs = {}
            for item in service["environment"]:
                key, value = item.split("=")
                if value.startswith("${") and value.endswith("}"):
                    value = devel_environ.get(value[2:-1], value)
                _environs[key] = value
            service["environment"] = [ "{}={}".format(k,v) for k,v in _environs.items() ]
    # updates current docker-compose (also versioned ... do not change by hand)
    with docker_compose_path.open('wt') as f:
        yaml.dump(content, f, default_flow_style=False)
