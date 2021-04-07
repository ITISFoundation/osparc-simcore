""" Fixtures to create docker-compose.yaml configururation files (as in Makefile)

    Basically runs `docker-compose config
"""
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import os
import shutil
import socket
import sys
from copy import deepcopy
from pathlib import Path
from pprint import pformat
from typing import Dict, Iterator, List

import pytest
import yaml
from dotenv import dotenv_values

from .helpers import (
    FIXTURE_CONFIG_CORE_SERVICES_SELECTION,
    FIXTURE_CONFIG_OPS_SERVICES_SELECTION,
)
from .helpers.utils_docker import run_docker_compose_config, save_docker_infos


@pytest.fixture(scope="session")
def devel_environ(env_devel_file: Path) -> Dict[str, str]:
    """
    Loads and extends .env-devel returning
    all environment variables key=value
    """
    env_devel_unresolved = dotenv_values(env_devel_file, verbose=True, interpolate=True)
    # get from environ if applicable
    env_devel = {
        key: os.environ.get(key, value) for key, value in env_devel_unresolved.items()
    }

    # These are overrides to .env-devel or an extension to them
    env_devel["LOG_LEVEL"] = "DEBUG"
    env_devel["REGISTRY_SSL"] = "False"
    env_devel["REGISTRY_URL"] = "{}:5000".format(_get_ip())
    env_devel["REGISTRY_PATH"] = "127.0.0.1:5000"
    env_devel["REGISTRY_USER"] = "simcore"
    env_devel["REGISTRY_PW"] = ""
    env_devel["REGISTRY_AUTH"] = "False"
    env_devel["SWARM_STACK_NAME"] = "simcore"
    env_devel["DIRECTOR_REGISTRY_CACHING"] = "False"
    env_devel["API_SERVER_DEV_FEATURES_ENABLED"] = "1"

    return env_devel


@pytest.fixture(scope="module")
def env_file(
    osparc_simcore_root_dir: Path, devel_environ: Dict[str, str]
) -> Iterator[Path]:
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


@pytest.fixture(scope="module")
def make_up_prod_environ():
    # TODO: use monkeypatch for modules as in https://github.com/pytest-dev/pytest/issues/363#issuecomment-289830794
    old_env = deepcopy(os.environ)
    if not "DOCKER_REGISTRY" in os.environ:
        os.environ["DOCKER_REGISTRY"] = "local"
    if not "DOCKER_IMAGE_TAG" in os.environ:
        os.environ["DOCKER_IMAGE_TAG"] = "production"
    yield
    os.environ = old_env


@pytest.fixture(scope="module")
def simcore_docker_compose(
    osparc_simcore_root_dir: Path,
    env_file: Path,
    temp_folder: Path,
    make_up_prod_environ,
) -> Dict:
    """Resolves docker-compose for simcore stack in local host

    Produces same as  `make .stack-simcore-version.yml` in a temporary folder
    """
    COMPOSE_FILENAMES = ["docker-compose.yml", "docker-compose.local.yml"]

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
    print("simcore docker-compose:\n%s", pformat(config))
    return config


@pytest.fixture(scope="module")
def ops_docker_compose(
    osparc_simcore_root_dir: Path, env_file: Path, temp_folder: Path
) -> Dict:
    """Filters only services in docker-compose-ops.yml and returns yaml data

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
    print("ops docker-compose:\n%s", pformat(config))
    return config


@pytest.fixture(scope="module")
def core_services_selection(request) -> List[str]:
    """ Selection of services from the simcore stack """
    core_services = getattr(request.module, FIXTURE_CONFIG_CORE_SERVICES_SELECTION, [])

    if "postgres" in core_services:
        assert (
            "pgbouncer" in core_services
        ), f"WARNING: the test is missing pgbouncer service in '{FIXTURE_CONFIG_CORE_SERVICES_SELECTION}' within '{request.module.__name__}'. postgres alone is not accessible!!"
    assert (
        core_services
    ), f"Expected at least one service in '{FIXTURE_CONFIG_CORE_SERVICES_SELECTION}' within '{request.module.__name__}'"
    return core_services


@pytest.fixture(scope="module")
def core_docker_compose_file(
    core_services_selection: List[str], temp_folder: Path, simcore_docker_compose: Dict
) -> Path:
    """Creates a docker-compose config file for every stack of services in'core_services' module variable
    File is created in a temp folder
    """
    docker_compose_path = Path(temp_folder / "simcore_docker_compose.filtered.yml")

    _filter_services_and_dump(
        core_services_selection, simcore_docker_compose, docker_compose_path
    )

    return docker_compose_path


@pytest.fixture(scope="module")
def ops_services_selection(request) -> List[str]:
    """ Selection of services from the ops stack """
    ops_services = getattr(request.module, FIXTURE_CONFIG_OPS_SERVICES_SELECTION, [])
    return ops_services


@pytest.fixture(scope="module")
def ops_docker_compose_file(
    ops_services_selection: List[str], temp_folder: Path, ops_docker_compose: Dict
) -> Path:
    """Creates a docker-compose config file for every stack of services in 'ops_services' module variable
    File is created in a temp folder
    """
    docker_compose_path = Path(temp_folder / "ops_docker_compose.filtered.yml")

    _filter_services_and_dump(
        ops_services_selection, ops_docker_compose, docker_compose_path
    )

    return docker_compose_path


# HELPERS ---------------------------------------------
def _minio_fix(service_environs: Dict) -> Dict:
    """this hack ensures that S3 is accessed from the host at all time, thus pre-signed links work."""
    if "S3_ENDPOINT" in service_environs:
        service_environs["S3_ENDPOINT"] = f"{_get_ip()}:9001"
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


@pytest.hookimpl()
def pytest_exception_interact(node, call, report):
    # get the node root dir (guaranteed to exist)
    root_directory: Path = Path(node.config.rootdir)
    failed_test_directory = root_directory / "test_failures" / node.name
    save_docker_infos(failed_test_directory)
