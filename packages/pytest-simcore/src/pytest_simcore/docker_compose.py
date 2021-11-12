# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

""" Fixtures to create docker-compose.yaml configuration files (as in Makefile)

    - Basically runs `docker-compose config
    - Services in stack can be selected using 'core_services_selection', 'ops_services_selection' fixtures
"""

import json
import os
import shutil
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Iterator, List

import pytest
import yaml
from _pytest.config import ExitCode
from dotenv import dotenv_values

from .helpers import (
    FIXTURE_CONFIG_CORE_SERVICES_SELECTION,
    FIXTURE_CONFIG_OPS_SERVICES_SELECTION,
)
from .helpers.constants import HEADER_STR
from .helpers.utils_docker import get_ip, run_docker_compose_config, save_docker_infos
from .helpers.utils_environs import EnvVarsDict


@pytest.fixture(scope="session")
def testing_environ_vars(env_devel_file: Path) -> EnvVarsDict:
    """
    Loads and extends .env-devel returning
    all environment variables key=value
    """
    env_devel_unresolved = dotenv_values(env_devel_file, verbose=True, interpolate=True)

    # get from environ if applicable
    env_devel: EnvVarsDict = {
        key: os.environ.get(key, value) for key, value in env_devel_unresolved.items()
    }

    # These are overrides to .env-devel or an extension to them
    env_devel["LOG_LEVEL"] = "DEBUG"

    env_devel["REGISTRY_SSL"] = "False"
    env_devel["REGISTRY_URL"] = "{}:5000".format(get_ip())
    env_devel["REGISTRY_PATH"] = "127.0.0.1:5000"
    env_devel["REGISTRY_USER"] = "simcore"
    env_devel["REGISTRY_PW"] = ""
    env_devel["REGISTRY_AUTH"] = "False"

    # CAREFUL! FIXME: monkeypatch autouse ??
    env_devel["SWARM_STACK_NAME"] = "pytest-simcore"
    env_devel.setdefault(
        "SWARM_STACK_NAME_NO_HYPHEN", env_devel["SWARM_STACK_NAME"].replace("-", "_")
    )

    env_devel["DIRECTOR_REGISTRY_CACHING"] = "False"
    env_devel.setdefault("DIRECTOR_SERVICES_CUSTOM_CONSTRAINTS", "")
    env_devel.setdefault("DIRECTOR_SELF_SIGNED_SSL_SECRET_ID", "")
    env_devel.setdefault("DIRECTOR_SELF_SIGNED_SSL_SECRET_NAME", "")
    env_devel.setdefault("DIRECTOR_SELF_SIGNED_SSL_FILENAME", "")

    env_devel["API_SERVER_DEV_FEATURES_ENABLED"] = "1"

    if not "DOCKER_REGISTRY" in os.environ:
        env_devel["DOCKER_REGISTRY"] = "local"
    if not "DOCKER_IMAGE_TAG" in os.environ:
        env_devel["DOCKER_IMAGE_TAG"] = "production"

    return env_devel


@pytest.fixture(scope="module")
def env_file_for_testing(
    testing_environ_vars: Dict[str, str],
    temp_folder: Path,
    osparc_simcore_root_dir: Path,
) -> Iterator[Path]:
    """Dumps all the environment variables into an $(temp_folder)/.env.test file

    Pass path as argument in 'docker-compose --env-file ... '
    """
    # SEE:
    #   https://docs.docker.com/compose/env-file/
    #   https://docs.docker.com/compose/environment-variables/#the-env-file

    env_test_path = temp_folder / ".env.test"

    with env_test_path.open("wt") as fh:
        print(
            f"# Auto-generated from env_file_for_testing in {__file__}",
            file=fh,
        )
        for key in sorted(testing_environ_vars.keys()):
            print(f"{key}={testing_environ_vars[key]}", file=fh)

    #
    # WARNING: since compose files have references to ../.env we MUST create .env
    #
    backup_path = osparc_simcore_root_dir / ".env.bak"
    env_path = osparc_simcore_root_dir / ".env"
    if env_path.exists():
        shutil.copy(env_path, backup_path)

    shutil.copy(env_test_path, env_path)

    yield env_path

    if backup_path.exists():
        backup_path.replace(env_path)


@pytest.fixture(scope="module")
def simcore_docker_compose(
    osparc_simcore_root_dir: Path,
    env_file_for_testing: Path,
    temp_folder: Path,
) -> Dict[str, Any]:
    """Resolves docker-compose for simcore stack in local host

    Produces same as  `make .stack-simcore-version.yml` in a temporary folder
    """
    COMPOSE_FILENAMES = ["docker-compose.yml", "docker-compose.local.yml"]

    # ensures .env at git_root_dir
    assert env_file_for_testing.exists()

    # target docker-compose path
    docker_compose_paths = [
        osparc_simcore_root_dir / "services" / filename
        for filename in COMPOSE_FILENAMES
    ]
    assert all(
        docker_compose_path.exists() for docker_compose_path in docker_compose_paths
    )

    config = run_docker_compose_config(
        project_dir=osparc_simcore_root_dir / "services",
        docker_compose_paths=docker_compose_paths,
        env_file_path=env_file_for_testing,
        destination_path=temp_folder / "simcore_docker_compose.yml",
    )
    # NOTE: do not add indent. Copy&Paste log into editor instead
    print(
        HEADER_STR.format("simcore docker-compose"),
        json.dumps(config),
        HEADER_STR.format("-"),
    )
    return config


@pytest.fixture(scope="module")
def ops_docker_compose(
    osparc_simcore_root_dir: Path, env_file_for_testing: Path, temp_folder: Path
) -> Dict[str, Any]:
    """Filters only services in docker-compose-ops.yml and returns yaml data

    Produces same as  `make .stack-ops.yml` in a temporary folder
    """
    # ensures .env at git_root_dir, which will be used as current directory
    assert env_file_for_testing.exists()

    # target docker-compose path
    docker_compose_path = (
        osparc_simcore_root_dir / "services" / "docker-compose-ops.yml"
    )
    assert docker_compose_path.exists()

    config = run_docker_compose_config(
        project_dir=osparc_simcore_root_dir / "services",
        docker_compose_paths=docker_compose_path,
        env_file_path=env_file_for_testing,
        destination_path=temp_folder / "ops_docker_compose.yml",
    )
    # NOTE: do not add indent. Copy&Paste log into editor instead
    print(
        HEADER_STR.format("ops docker-compose"),
        json.dumps(config),
        HEADER_STR.format("-"),
    )
    return config


@pytest.fixture(scope="module")
def core_services_selection(request) -> List[str]:
    """Selection of services from the simcore stack"""
    core_services = getattr(request.module, FIXTURE_CONFIG_CORE_SERVICES_SELECTION, [])

    assert (
        core_services
    ), f"Expected at least one service in '{FIXTURE_CONFIG_CORE_SERVICES_SELECTION}' within '{request.module.__name__}'"
    return core_services


@pytest.fixture(scope="module")
def core_docker_compose_file(
    core_services_selection: List[str], temp_folder: Path, simcore_docker_compose: Dict
) -> Path:
    """A compose with a selection of services from simcore_docker_compose

    Creates a docker-compose config file for every stack of services in 'core_services_selection' module variable
    File is created in a temp folder
    """
    docker_compose_path = Path(temp_folder / "simcore_docker_compose.filtered.yml")

    _filter_services_and_dump(
        core_services_selection, simcore_docker_compose, docker_compose_path
    )

    return docker_compose_path


@pytest.fixture(scope="module")
def ops_services_selection(request) -> List[str]:
    """Selection of services from the ops stack"""
    ops_services = getattr(request.module, FIXTURE_CONFIG_OPS_SERVICES_SELECTION, [])
    return ops_services


@pytest.fixture(scope="module")
def ops_docker_compose_file(
    ops_services_selection: List[str], temp_folder: Path, ops_docker_compose: Dict
) -> Path:
    """A compose with a selection of services from ops_docker_compose

    Creates a docker-compose config file for every stack of services in 'ops_services_selection' module variable
    File is created in a temp folder
    """
    docker_compose_path = Path(temp_folder / "ops_docker_compose.filtered.yml")

    _filter_services_and_dump(
        ops_services_selection, ops_docker_compose, docker_compose_path
    )

    return docker_compose_path


@pytest.hookimpl()
def pytest_exception_interact(node, call, report):
    # get the node root dir (guaranteed to exist)
    root_directory: Path = Path(node.config.rootdir)
    failed_test_directory = root_directory / "test_failures" / node.name
    save_docker_infos(failed_test_directory)


@pytest.hookimpl()
def pytest_sessionfinish(session: pytest.Session, exitstatus: ExitCode) -> None:
    if exitstatus == ExitCode.TESTS_FAILED:
        root_directory: Path = Path(session.fspath)
        failed_test_directory = root_directory / "test_failures" / session.name
        save_docker_infos(failed_test_directory)


# HELPERS ---------------------------------------------


def _minio_fix(service_environs: Dict) -> Dict:
    """this hack ensures that S3 is accessed from the host at all time, thus pre-signed links work."""
    if "S3_ENDPOINT" in service_environs:
        service_environs["S3_ENDPOINT"] = f"{get_ip()}:9001"
    return service_environs


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
