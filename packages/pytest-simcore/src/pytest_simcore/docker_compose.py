""" Fixtures to create docker-compose.yaml configururation files (as in Makefile)

    Basically runs `docker-compose config
"""
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import os
import re
import shutil
import socket
import sys
from copy import deepcopy
from pathlib import Path
from typing import Dict, List

import pytest
import yaml

from .helpers.utils_docker import run_docker_compose_config


@pytest.fixture("session")
def devel_environ(env_devel_file: Path) -> Dict[str, str]:
    """ Loads and extends .env-devel returning
        all environment variables key=value
    """
    key_eq_value_pattern = re.compile(r"^(\w+)=(.*)$")
    env_devel = {}
    with env_devel_file.open() as fh:
        for line in fh:
            match = key_eq_value_pattern.match(line)
            if match:
                key, value = match.groups()
                env_devel[key] = str(value)

    # Customized EXTENSION: overrides some of the environ to accomodate the test case ----
    if "REGISTRY_SSL" in env_devel:
        env_devel["REGISTRY_SSL"] = "False"
    if "REGISTRY_URL" in env_devel:
        env_devel["REGISTRY_URL"] = "{}:5000".format(_get_ip())
    if "REGISTRY_USER" in env_devel:
        env_devel["REGISTRY_USER"] = "simcore"
    if "REGISTRY_PW" in env_devel:
        env_devel["REGISTRY_PW"] = ""
    if "REGISTRY_AUTH" in env_devel:
        env_devel["REGISTRY_AUTH"] = False

    if "SWARM_STACK_NAME" not in os.environ:
        env_devel["SWARM_STACK_NAME"] = "simcore"

    return env_devel


@pytest.fixture(scope="module")
def env_file(osparc_simcore_root_dir: Path, devel_environ: Dict[str, str]) -> Path:
    """
        Creates a .env file from the .env-devel
    """
    # preserves .env at git_root_dir after test if already exists
    env_path = osparc_simcore_root_dir / ".env"
    backup_path = osparc_simcore_root_dir / ".env.bak"
    if env_path.exists():
        shutil.copy(env_path, backup_path)

    with env_path.open("wt") as fh:
        print(f"# TEMPORARY .env auto-generated from env_path in {__file__}")
        for key, value in devel_environ.items():
            print(f"{key}={value}", file=fh)

    yield env_path

    env_path.unlink()
    if backup_path.exists():
        shutil.copy(backup_path, env_path)
        backup_path.unlink()


@pytest.fixture("module")
def simcore_docker_compose(
    osparc_simcore_root_dir: Path, env_file: Path, temp_folder: Path
) -> Dict:
    """ Resolves docker-compose for simcore stack in local host

        Produces same as  `make .stack-simcore-version.yml` in a temporary folder
    """
    COMPOSE_FILENAMES = ["docker-compose.yml", "docker-compose.local.yml"]

    os.environ["DOCKER_REGISTRY"] = "local"
    os.environ["DOCKER_IMAGE_TAG"] = "production"
    # ensures .env at git_root_dir
    assert env_file.exists()
    assert env_file.parent == osparc_simcore_root_dir

    # target docker-compose path
    docker_compose_paths = [
        osparc_simcore_root_dir / "services" / filename
        for filename in COMPOSE_FILENAMES
    ]
    assert all(
        docker_compose_path.exists() for docker_compose_path in docker_compose_paths
    )

    config = run_docker_compose_config(
        docker_compose_paths,
        workdir=env_file.parent,
        destination_path=temp_folder / "simcore_docker_compose.yml",
    )

    return config


@pytest.fixture("module")
def ops_docker_compose(
    osparc_simcore_root_dir: Path, env_file: Path, temp_folder: Path
) -> Dict:
    """ Filters only services in docker-compose-ops.yml and returns yaml data

        Produces same as  `make .stack-ops.yml` in a temporary folder
    """
    # ensures .env at git_root_dir, which will be used as current directory
    assert env_file.exists()
    assert env_file.parent == osparc_simcore_root_dir

    # target docker-compose path
    docker_compose_path = (
        osparc_simcore_root_dir / "services" / "docker-compose-ops.yml"
    )
    assert docker_compose_path.exists()

    config = run_docker_compose_config(
        docker_compose_path,
        workdir=env_file.parent,
        destination_path=temp_folder / "ops_docker_compose.yml",
    )
    return config


@pytest.fixture(scope="module")
def core_services_config_file(request, temp_folder, simcore_docker_compose):
    """ Creates a docker-compose config file for every stack of services in'core_services' module variable
        File is created in a temp folder
    """
    core_services = getattr(
        request.module, "core_services", []
    )  # TODO: PC->SAN could also be defined as a fixture instead of a single variable (as with docker_compose)
    assert (
        core_services
    ), f"Expected at least one service in 'core_services' within '{request.module.__name__}'"

    docker_compose_path = Path(temp_folder / "simcore_docker_compose.filtered.yml")

    _filter_services_and_dump(
        core_services, simcore_docker_compose, docker_compose_path
    )

    return docker_compose_path


@pytest.fixture(scope="module")
def ops_services_config_file(request, temp_folder, ops_docker_compose):
    """ Creates a docker-compose config file for every stack of services in 'ops_services' module variable
        File is created in a temp folder
    """
    ops_services = getattr(request.module, "ops_services", [])
    docker_compose_path = Path(temp_folder / "ops_docker_compose.filtered.yml")

    _filter_services_and_dump(ops_services, ops_docker_compose, docker_compose_path)

    return docker_compose_path


# HELPERS ---------------------------------------------
def _minio_fix(service_environs: Dict) -> Dict:
    """this hack ensures that S3 is accessed from the host at all time, thus pre-signed links work.
        172.17.0.1 is the docker0 interface, which redirect from inside a container onto the host network interface.
    """
    if "S3_ENDPOINT" in service_environs:
        service_environs["S3_ENDPOINT"] = "172.17.0.1:9001"
    return service_environs


def _get_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't even have to be reachable
        s.connect(("10.255.255.255", 1))
        IP = s.getsockname()[0]
    except Exception:  # pylint: disable=W0703
        IP = "127.0.0.1"
    finally:
        s.close()
    return IP


def _filter_services_and_dump(
    include: List, services_compose: Dict, docker_compose_path: Path
):
    content = deepcopy(services_compose)

    # filters services
    remove = [name for name in content["services"] if name not in include]
    for name in remove:
        content["services"].pop(name, None)

    for name in include:
        service = content["services"][name]
        # removes builds (No more)
        if "build" in service:
            service.pop("build", None)
        if "environment" in service:
            service["environment"] = _minio_fix(service["environment"])

    # updates current docker-compose (also versioned ... do not change by hand)
    with docker_compose_path.open("wt") as fh:
        if "TRAVIS" in os.environ:
            # in travis we do not have access to file
            print("{:-^100}".format(str(docker_compose_path)))
            yaml.dump(content, sys.stdout, default_flow_style=False)
            print("-" * 100)
        else:
            # locally we have access to file
            print(f"Saving config to '{docker_compose_path}'")
        yaml.dump(content, fh, default_flow_style=False)
