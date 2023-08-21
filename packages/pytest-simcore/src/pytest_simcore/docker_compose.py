# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

""" Fixtures to create docker-compose.yaml configuration files (as in Makefile)

    - Basically runs `docker compose config
    - Services in stack can be selected using 'core_services_selection', 'ops_services_selection' fixtures

"""

import json
import os
import re
import shutil
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterator

import pytest
import yaml
from dotenv import dotenv_values, set_key
from pytest import ExitCode

from .helpers import (
    FIXTURE_CONFIG_CORE_SERVICES_SELECTION,
    FIXTURE_CONFIG_OPS_SERVICES_SELECTION,
)
from .helpers.constants import HEADER_STR
from .helpers.typing_env import EnvVarsDict
from .helpers.utils_docker import (
    get_localhost_ip,
    run_docker_compose_config,
    save_docker_infos,
)


@pytest.fixture(scope="session")
def testing_environ_vars(env_devel_file: Path) -> EnvVarsDict:
    """
    Loads and extends .env-devel returning
    all environment variables key=value
    """
    env_devel = dotenv_values(
        env_devel_file,
        verbose=True,
        interpolate=True,  # NOTE: This resolves expressions as VAR=$ENVVAR
    )

    # These are overrides to .env-devel or an extension to them
    env_devel["LOG_LEVEL"] = "DEBUG"

    env_devel["REGISTRY_SSL"] = "False"
    env_devel["REGISTRY_URL"] = f"{get_localhost_ip()}:5000"
    env_devel["REGISTRY_PATH"] = "127.0.0.1:5000"
    env_devel["REGISTRY_USER"] = "simcore"
    env_devel["REGISTRY_PW"] = ""
    env_devel["REGISTRY_AUTH"] = "False"

    env_devel["SWARM_STACK_NAME"] = "pytest-simcore"
    env_devel.setdefault(
        "SWARM_STACK_NAME_NO_HYPHEN", env_devel["SWARM_STACK_NAME"].replace("-", "_")
    )

    env_devel[
        "AIOCACHE_DISABLE"
    ] = "1"  # ensure that aio-caches are disabled for testing [https://aiocache.readthedocs.io/en/latest/testing.html]
    env_devel[
        "CATALOG_BACKGROUND_TASK_REST_TIME"
    ] = "1"  # ensure catalog refreshes services access rights fast

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

    return {key: value for key, value in env_devel.items() if value is not None}


@pytest.fixture(scope="module")
def env_file_for_testing(
    testing_environ_vars: dict[str, str],
    temp_folder: Path,
    osparc_simcore_root_dir: Path,
) -> Iterator[Path]:
    """Dumps all the environment variables into an $(temp_folder)/.env.test file

    Pass path as argument in 'docker compose --env-file ... '
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
    osparc_simcore_scripts_dir: Path,
    env_file_for_testing: Path,
    temp_folder: Path,
) -> dict[str, Any]:
    """Resolves docker-compose for simcore stack in local host

    Produces same as  `make .stack-simcore-version.yml` in a temporary folder
    """
    COMPOSE_FILENAMES = ["docker-compose.yml", "docker-compose.local.yml"]

    # ensures .env at git_root_dir
    assert env_file_for_testing.exists()

    # target docker compose path
    docker_compose_paths = [
        osparc_simcore_root_dir / "services" / filename
        for filename in COMPOSE_FILENAMES
    ]
    assert all(
        docker_compose_path.exists() for docker_compose_path in docker_compose_paths
    )

    compose_specs = run_docker_compose_config(
        project_dir=osparc_simcore_root_dir / "services",
        scripts_dir=osparc_simcore_scripts_dir,
        docker_compose_paths=docker_compose_paths,
        env_file_path=env_file_for_testing,
        destination_path=temp_folder / "simcore_docker_compose.yml",
    )
    # NOTE: do not add indent. Copy&Paste log into editor instead
    print(
        HEADER_STR.format("simcore docker-compose"),
        json.dumps(compose_specs),
        HEADER_STR.format("-"),
    )
    return compose_specs


@pytest.fixture(scope="module")
def inject_filestash_config_path_env(
    osparc_simcore_scripts_dir: Path,
    env_file_for_testing: Path,
) -> EnvVarsDict:
    create_filestash_config_py = (
        osparc_simcore_scripts_dir / "filestash" / "create_config.py"
    )

    # ensures .env at git_root_dir, which will be used as current directory
    assert env_file_for_testing.exists()
    env_values = dotenv_values(env_file_for_testing)

    process = subprocess.run(
        ["python3", f"{create_filestash_config_py}"],
        shell=False,
        check=True,
        stdout=subprocess.PIPE,
        env=env_values,
    )
    filestash_config_json_path = Path(process.stdout.decode("utf-8").strip())
    assert filestash_config_json_path.exists()

    set_key(
        env_file_for_testing,
        "TMP_PATH_TO_FILESTASH_CONFIG",
        f"{filestash_config_json_path}",
    )
    return {"TMP_PATH_TO_FILESTASH_CONFIG": f"{filestash_config_json_path}"}


@pytest.fixture(scope="module")
def ops_docker_compose(
    osparc_simcore_root_dir: Path,
    osparc_simcore_scripts_dir: Path,
    env_file_for_testing: Path,
    temp_folder: Path,
    inject_filestash_config_path_env: dict[str, str],
) -> dict[str, Any]:
    """Filters only services in docker-compose-ops.yml and returns yaml data

    Produces same as  `make .stack-ops.yml` in a temporary folder
    """
    # ensures .env at git_root_dir, which will be used as current directory
    assert env_file_for_testing.exists()

    # target docker compose path
    docker_compose_path = (
        osparc_simcore_root_dir / "services" / "docker-compose-ops.yml"
    )
    assert docker_compose_path.exists()

    compose_specs = run_docker_compose_config(
        project_dir=osparc_simcore_root_dir / "services",
        scripts_dir=osparc_simcore_scripts_dir,
        docker_compose_paths=docker_compose_path,
        env_file_path=env_file_for_testing,
        destination_path=temp_folder / "ops_docker_compose.yml",
        additional_envs=inject_filestash_config_path_env,
    )
    # NOTE: do not add indent. Copy&Paste log into editor instead
    print(
        HEADER_STR.format("ops docker-compose"),
        json.dumps(compose_specs),
        HEADER_STR.format("-"),
    )
    return compose_specs


@pytest.fixture(scope="module")
def core_services_selection(request) -> list[str]:
    """Selection of services from the simcore stack"""
    core_services = getattr(request.module, FIXTURE_CONFIG_CORE_SERVICES_SELECTION, [])

    assert (
        core_services
    ), f"Expected at least one service in '{FIXTURE_CONFIG_CORE_SERVICES_SELECTION}' within '{request.module.__name__}'"
    return core_services


@pytest.fixture(scope="module")
def core_docker_compose_file(
    core_services_selection: list[str], temp_folder: Path, simcore_docker_compose: dict
) -> Path:
    """A compose with a selection of services from simcore_docker_compose

    Creates a docker compose config file for every stack of services in 'core_services_selection' module variable
    File is created in a temp folder
    """
    docker_compose_path = Path(temp_folder / "simcore_docker_compose.filtered.yml")

    _filter_services_and_dump(
        core_services_selection, simcore_docker_compose, docker_compose_path
    )

    return docker_compose_path


@pytest.fixture(scope="module")
def ops_services_selection(request) -> list[str]:
    """Selection of services from the ops stack"""
    ops_services = getattr(request.module, FIXTURE_CONFIG_OPS_SERVICES_SELECTION, [])
    return ops_services


@pytest.fixture(scope="module")
def ops_docker_compose_file(
    ops_services_selection: list[str], temp_folder: Path, ops_docker_compose: dict
) -> Path:
    """A compose with a selection of services from ops_docker_compose

    Creates a docker compose config file for every stack of services in 'ops_services_selection' module variable
    File is created in a temp folder
    """
    docker_compose_path = Path(temp_folder / "ops_docker_compose.filtered.yml")

    # these services are useless when running in the CI
    ops_view_only_services = ["adminer", "redis-commander", "portainer", "filestash"]
    if "CI" in os.environ:
        print(
            f"WARNING: Services such as {ops_view_only_services!r} are removed from the stack when running in the CI"
        )
        ops_services_selection = list(
            filter(
                lambda item: item not in ops_view_only_services, ops_services_selection
            )
        )

    _filter_services_and_dump(
        ops_services_selection, ops_docker_compose, docker_compose_path
    )

    return docker_compose_path


def _save_docker_logs_to_folder(failed_test_directory: Path):
    try:
        save_docker_infos(failed_test_directory)
    except OSError as exc:
        if exc.errno == 36:  # OSError [Errno 36] File name too long
            short_name = f"{failed_test_directory.name[:5]}_{hash(failed_test_directory.name)}_{failed_test_directory.name[-5:]}"
            failed_test_directory = failed_test_directory.parent / short_name

            save_docker_infos(failed_test_directory)
        else:
            raise


@pytest.hookimpl()
def pytest_exception_interact(node, call, report):
    # get the node root dir (guaranteed to exist)
    root_directory: Path = Path(node.config.rootdir)
    failed_test_directory = root_directory / "test_failures" / node.name
    _save_docker_logs_to_folder(failed_test_directory)


@pytest.hookimpl()
def pytest_sessionfinish(session: pytest.Session, exitstatus: ExitCode) -> None:
    if exitstatus == ExitCode.TESTS_FAILED:
        root_directory: Path = Path(session.fspath)
        failed_test_directory = root_directory / "test_failures" / session.name
        _save_docker_logs_to_folder(failed_test_directory)


def _minio_fix(service_environs: dict) -> dict:
    """this hack ensures that S3 is accessed from the host at all time, thus pre-signed links work."""
    if "S3_ENDPOINT" in service_environs:
        service_environs["S3_ENDPOINT"] = f"{get_localhost_ip()}:9001"
    return service_environs


def _escape_cpus(serialized_yaml: str) -> str:
    # NOTE: fore details on below SEE
    # https://github.com/docker/compose/issues/7771#issuecomment-765243575
    # below is equivalent to the following sed operation fixes above issue
    # `sed -E "s/cpus: ([0-9\\.]+)/cpus: '\\1'/"`
    # remove when this issues is fixed, this will most likely occur
    # when upgrading the version of docker compose

    return re.sub(
        pattern=r"cpus: (\d+\.\d+|\d+)", repl="cpus: '\\1'", string=serialized_yaml
    )


def _filter_services_and_dump(
    include: list, services_compose: dict, docker_compose_path: Path
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
            print(f"{str(docker_compose_path):-^100}")
            yaml.dump(content, sys.stdout, default_flow_style=False)
            print("-" * 100)
        else:
            # locally we have access to file
            print(f"Saving config to '{docker_compose_path}'")
        yaml.dump(content, fh, default_flow_style=False)

    docker_compose_path.write_text(_escape_cpus(docker_compose_path.read_text()))
