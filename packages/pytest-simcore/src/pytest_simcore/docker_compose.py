# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

"""Fixtures to create docker-compose.yaml configuration files (as in Makefile)

- Basically runs `docker compose config
- Services in stack can be selected using 'core_services_selection', 'ops_services_selection' fixtures

"""

import logging
import os
import re
import shutil
from collections.abc import Iterator
from copy import deepcopy
from datetime import timedelta
from io import StringIO
from pathlib import Path
from typing import Any, Final
from urllib.parse import urlsplit

import pytest
import yaml
from dotenv import dotenv_values

from .helpers import (
    FIXTURE_CONFIG_CORE_SERVICES_SELECTION,
    FIXTURE_CONFIG_OPS_SERVICES_SELECTION,
)
from .helpers.dev_slot import DevSlotMismatchError, lease_checkout_slot, load_dev_slot_module
from .helpers.docker import filter_service_names_for_ci, run_docker_compose_config, save_docker_infos
from .helpers.host import get_localhost_ip
from .helpers.stack_names import compute_stack_names, get_git_ref
from .helpers.typing_env import EnvVarsDict
from .helpers.xdist import (
    is_xdist_controller,
    is_xdist_worker,
    read_shared_resources,
    record_shared_resource,
    run_once_across_workers,
)

_logger = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def temp_folder(request: pytest.FixtureRequest, tmp_path_factory: pytest.TempPathFactory) -> Path:
    """**Module scoped** temporary folder"""
    prefix = __name__.replace(".", "_")
    return tmp_path_factory.mktemp(basename=f"{prefix}_temp_folder_{request.module.__name__}", numbered=True)


@pytest.fixture(scope="session")
def env_vars_for_docker_compose(
    env_devel_file: Path,
    osparc_simcore_root_dir: Path,
) -> EnvVarsDict:
    """
    Loads and extends .env-devel returning all environment variables key=value

    The slot's variables (host ports, ...) are prepended to .env-devel so that
    its ${VAR:-default} values (e.g. S3_ENDPOINT) resolve to this checkout's slot.

    NOTE: that these are then env-vars used in the services started in the
    integration tests!
    """
    is_ci = "CI" in os.environ
    try:
        slot = lease_checkout_slot(osparc_simcore_root_dir, accept_moved_slot=is_ci)
    except DevSlotMismatchError as err:
        pytest.exit(f"{err}", returncode=pytest.ExitCode.USAGE_ERROR)
    dev_slot = load_dev_slot_module(osparc_simcore_root_dir)
    slot_env: dict[str, str] = dev_slot.derive_env(slot)

    slot_lines = "".join(f"{key}={value}\n" for key, value in slot_env.items())
    env_devel = dotenv_values(
        stream=StringIO(slot_lines + env_devel_file.read_text()),
        verbose=True,
        interpolate=True,  # NOTE: This resolves expressions as VAR=$ENVVAR
    )
    env_devel |= slot_env  # .env-devel redefines some of them with slot-0 values

    # These are overrides to .env-devel or an extension to them
    env_devel["LOG_LEVEL"] = "DEBUG"

    env_devel["REGISTRY_SSL"] = "False"
    env_devel["REGISTRY_URL"] = f"{get_localhost_ip()}:5000"
    env_devel["REGISTRY_PATH"] = "127.0.0.1:5000"
    env_devel["REGISTRY_USER"] = "simcore"
    env_devel["REGISTRY_PW"] = ""
    env_devel["REGISTRY_AUTH"] = "False"

    # stack names are daemon-global: one pair per slot, named after the branch for humans
    core_stack_name, ops_stack_name = compute_stack_names(slot, get_git_ref(osparc_simcore_root_dir))
    env_devel["SWARM_STACK_NAME"] = core_stack_name
    env_devel["SWARM_OPS_STACK_NAME"] = ops_stack_name
    env_devel.setdefault("SWARM_STACK_NAME_NO_HYPHEN", env_devel["SWARM_STACK_NAME"].replace("-", "_"))

    # traefik's swarm provider selects services by this label ONLY, and labels are
    # daemon-global: with two checkouts deployed, each stack's traefik would discover the
    # other's routers (same rules, same priorities) and round-robin onto foreign backends
    env_devel["TRAEFIK_SIMCORE_ZONE"] = core_stack_name

    env_devel[
        "AIOCACHE_DISABLE"
        # ensure that aio-caches are disabled for testing [https://aiocache.readthedocs.io/en/latest/testing.html]
    ] = "1"
    env_devel[
        "CATALOG_BACKGROUND_TASK_REST_TIME"
        # ensure catalog refreshes services access rights fast
    ] = "1"

    # TRACING
    #  NOTE: should go away with pydantic v2
    env_devel["TRACING_OPENTELEMETRY_COLLECTOR_ENDPOINT"] = "null"
    env_devel["TRACING_OPENTELEMETRY_COLLECTOR_PORT"] = "null"

    # DIRECTOR
    env_devel["DIRECTOR_REGISTRY_CACHING"] = "False"
    # NOTE: this will make TracingSettings fail and therefore the default factory of every *_TRACING field will be set to None

    # NOTE: DIRECTOR_DEFAULT_MAX_* used for integration-tests that include `director` service
    env_devel["DIRECTOR_DEFAULT_MAX_MEMORY"] = "268435456"
    env_devel["DIRECTOR_DEFAULT_MAX_NANO_CPUS"] = "10000000"
    env_devel["DIRECTOR_LOGLEVEL"] = "DEBUG"
    env_devel["REGISTRY_PATH"] = "127.0.0.1:5000"

    env_devel["API_SERVER_DEV_FEATURES_ENABLED"] = "1"

    if "DOCKER_REGISTRY" not in os.environ:
        env_devel["DOCKER_REGISTRY"] = "local"
    if "DOCKER_IMAGE_TAG" not in os.environ:
        # local builds are tagged per slot; CI loads plain 'production' images
        env_devel["DOCKER_IMAGE_TAG"] = "production" + ("" if is_ci else slot_env["LOCAL_IMAGE_TAG_SUFFIX"])

    # ensure we do not use the bucket of simcore or so
    env_devel["S3_BUCKET_NAME"] = "pytestbucket"

    # ensure OpenTelemetry is not enabled
    env_devel |= dict.fromkeys(
        (
            "AGENT_TRACING",
            "API_SERVER_TRACING",
            "AUTOSCALING_TRACING",
            "CATALOG_TRACING",
            "CLUSTERS_KEEPER_TRACING",
            "DATCORE_ADAPTER_TRACING",
            "DIRECTOR_TRACING",
            "DIRECTOR_V2_TRACING",
            "DYNAMIC_SCHEDULER_TRACING",
            "INVITATIONS_TRACING",
            "PAYMENTS_TRACING",
            "RESOURCE_USAGE_TRACKER_TRACING",
            "STORAGE_TRACING",
            "WB_DB_EL_TRACING",
            "WB_GC_TRACING",
            "WEBSERVER_TRACING",
        ),
        "null",
    )

    return {key: value for key, value in env_devel.items() if value is not None}


@pytest.fixture(scope="module")
def env_file_for_docker_compose(
    temp_folder: Path,
    env_vars_for_docker_compose: EnvVarsDict,
    osparc_simcore_root_dir: Path,
    request: pytest.FixtureRequest,
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[Path]:
    """Dumps all the environment variables into an $(temp_folder)/.env.test file

    Pass path as argument in 'docker compose --env-file ... '

    Under xdist the repo-root .env is shared by all workers and its content is the same for the whole run,
    so the first worker writes it once and the controller restores the original at session end.
    """
    # WARNING: since compose files have references to ../.env we MUST create .env
    backup_path = osparc_simcore_root_dir / ".env.bak"
    env_path = osparc_simcore_root_dir / ".env"

    with run_once_across_workers(
        request, tmp_path_factory, "env_file_for_docker_compose", timeout=timedelta(minutes=1)
    ) as is_first:
        if is_first:
            # SEE:
            #   https://docs.docker.com/compose/env-file/
            #   https://docs.docker.com/compose/environment-variables/#the-env-file
            env_test_path = temp_folder / ".env.test"
            with env_test_path.open("wt") as fh:
                print(
                    f"# Auto-generated from env_file_for_testing in {__file__}",
                    file=fh,
                )
                for key, value in sorted(env_vars_for_docker_compose.items()):
                    # NOTE: python-dotenv parses JSON encoded strings correctly, but
                    # writing them back shows an issue. if the original ENV is something like
                    #   MY_ENV='{"correct": "encodedjson"}'
                    # it goes to MY_ENV={"incorrect": "encodedjson"}!
                    if value.startswith(("{", "[")) and value.endswith(("}", "]")):
                        print(f"{key}='{value}'", file=fh)
                    else:
                        print(f"{key}={value}", file=fh)

            had_env = env_path.exists()
            if had_env:
                shutil.copy(env_path, backup_path)

            # replace is atomic: concurrent `docker compose config` must never read a partial file
            staging_path = env_path.with_name(".env.staging")
            shutil.copy(env_test_path, staging_path)
            staging_path.replace(env_path)

            record_shared_resource(
                request,
                tmp_path_factory,
                kind="env_file",
                path=f"{env_path}",
                backup=f"{backup_path}" if had_env else "",
            )

    yield env_path

    if is_xdist_worker(request):
        return  # the xdist controller restores it at session end (see `pytest_sessionfinish`)

    if backup_path.exists():
        backup_path.replace(env_path)


@pytest.fixture(scope="module")
def simcore_docker_compose(
    osparc_simcore_root_dir: Path,
    osparc_simcore_scripts_dir: Path,
    env_file_for_docker_compose: Path,
    temp_folder: Path,
) -> dict[str, Any]:
    """Resolves docker-compose for simcore stack in local host

    Produces same as  `make .stack-simcore-version.yml` in a temporary folder
    """
    COMPOSE_FILENAMES = ["docker-compose.yml", "docker-compose.local.yml"]

    # ensures .env at git_root_dir
    assert env_file_for_docker_compose.exists()

    # target docker compose path
    docker_compose_paths = [osparc_simcore_root_dir / "services" / filename for filename in COMPOSE_FILENAMES]
    assert all(docker_compose_path.exists() for docker_compose_path in docker_compose_paths)

    return run_docker_compose_config(
        project_dir=osparc_simcore_root_dir / "services",
        scripts_dir=osparc_simcore_scripts_dir,
        docker_compose_paths=docker_compose_paths,
        env_file_path=env_file_for_docker_compose,
        destination_path=temp_folder / "simcore_docker_compose.yml",
    )


@pytest.fixture(scope="module")
def ops_docker_compose(
    osparc_simcore_root_dir: Path,
    osparc_simcore_scripts_dir: Path,
    env_file_for_docker_compose: Path,
    temp_folder: Path,
) -> dict[str, Any]:
    """Filters only services in docker-compose-ops.yml and returns yaml data

    Produces same as  `make .stack-ops.yml` in a temporary folder
    """
    # ensures .env at git_root_dir, which will be used as current directory
    assert env_file_for_docker_compose.exists()

    # target docker compose path
    docker_compose_path = osparc_simcore_root_dir / "services" / "docker-compose-ops.yml"
    assert docker_compose_path.exists()

    return run_docker_compose_config(
        project_dir=osparc_simcore_root_dir / "services",
        scripts_dir=osparc_simcore_scripts_dir,
        docker_compose_paths=docker_compose_path,
        env_file_path=env_file_for_docker_compose,
        destination_path=temp_folder / "ops_docker_compose.yml",
    )


@pytest.fixture(scope="module")
def core_services_selection(request) -> list[str]:
    """Selection of services from the simcore stack"""
    core_services = getattr(request.module, FIXTURE_CONFIG_CORE_SERVICES_SELECTION, [])

    assert core_services, (
        f"Expected at least one service in '{FIXTURE_CONFIG_CORE_SERVICES_SELECTION}' "
        f"within '{request.module.__name__}'"
    )
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

    _filter_services_and_dump(core_services_selection, simcore_docker_compose, docker_compose_path)

    _logger.info(
        "Content of '%s':\n%s",
        docker_compose_path,
        docker_compose_path.read_text(),
    )
    return docker_compose_path


@pytest.fixture(scope="module")
def ops_services_selection(request) -> list[str]:
    """Selection of services from the ops stack"""
    return getattr(request.module, FIXTURE_CONFIG_OPS_SERVICES_SELECTION, [])


_CI_ALLOWED_OPS_SERVICE_NAMES: Final[tuple[str, ...]] = ("s3-storage",)


@pytest.fixture(scope="module")
def ops_docker_compose_file(ops_services_selection: list[str], temp_folder: Path, ops_docker_compose: dict) -> Path:
    """A compose with a selection of services from ops_docker_compose

    Creates a docker compose config file for every stack of services in 'ops_services_selection' module variable
    File is created in a temp folder
    """
    docker_compose_path = Path(temp_folder / "ops_docker_compose.filtered.yml")

    ops_services_selection = filter_service_names_for_ci(ops_services_selection, _CI_ALLOWED_OPS_SERVICE_NAMES)

    _filter_services_and_dump(ops_services_selection, ops_docker_compose, docker_compose_path)

    _logger.info(
        "Content of '%s':\n%s",
        docker_compose_path,
        docker_compose_path.read_text(),
    )
    return docker_compose_path


def _save_docker_logs_to_folder(failed_test_directory: Path):
    try:
        save_docker_infos(failed_test_directory)
    except OSError as exc:
        if exc.errno == 36:  # OSError [Errno 36] File name too long
            short_name = (
                f"{failed_test_directory.name[:5]}_{hash(failed_test_directory.name)}_{failed_test_directory.name[-5:]}"
            )
            failed_test_directory = failed_test_directory.parent / short_name

            save_docker_infos(failed_test_directory)
        else:
            raise


@pytest.hookimpl()
def pytest_exception_interact(node, call: pytest.CallInfo[Any], report: pytest.CollectReport):
    # get the node root dir (guaranteed to exist)
    root_directory: Path = Path(node.config.rootdir)
    failed_test_directory = root_directory / "test_failures" / node.name
    _save_docker_logs_to_folder(failed_test_directory)


@pytest.hookimpl()
def pytest_sessionfinish(session: pytest.Session, exitstatus: pytest.ExitCode) -> None:
    if exitstatus == pytest.ExitCode.TESTS_FAILED:
        root_directory: Path = Path(session.fspath)
        failed_test_directory = root_directory / "test_failures" / session.name
        _save_docker_logs_to_folder(failed_test_directory)

    if is_xdist_controller(session.config):
        for resource in read_shared_resources(session.config):
            if resource["kind"] == "env_file" and resource["backup"]:
                Path(resource["backup"]).replace(resource["path"])


def _fix_s3_endpoint_to_host(service_environs: dict[str, str]) -> dict[str, str]:
    """this hack ensures that S3 is accessed from the host at all time, thus pre-signed links work.

    Keeps the port, which is the slot's S3 host port.
    """
    if "S3_ENDPOINT" in service_environs:
        port = urlsplit(service_environs["S3_ENDPOINT"]).port
        assert port, f"S3_ENDPOINT={service_environs['S3_ENDPOINT']!r} has no host port"
        service_environs["S3_ENDPOINT"] = f"http://{get_localhost_ip()}:{port}"
    return service_environs


def _escape_cpus(serialized_yaml: str) -> str:
    # NOTE: fore details on below SEE
    # https://github.com/docker/compose/issues/7771#issuecomment-765243575
    # below is equivalent to the following sed operation fixes above issue
    # `sed -E "s/cpus: ([0-9\\.]+)/cpus: '\\1'/"`
    # remove when this issues is fixed, this will most likely occur
    # when upgrading the version of docker compose

    return re.sub(pattern=r"cpus: (\d+\.\d+|\d+)", repl="cpus: '\\1'", string=serialized_yaml)


def _filter_services_and_dump(include: list, services_compose: dict, docker_compose_path: Path):
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
            service["environment"] = _fix_s3_endpoint_to_host(service["environment"])

        if name == "postgres":
            # NOTE: # -c fsync=off is not recommended for production as this disable writing to disk https://pythonspeed.com/articles/faster-db-tests/
            service["command"] += ["-c", "fsync=off"]

    # updates current docker-compose (also versioned ... do not change by hand)
    with docker_compose_path.open("wt") as fh:
        yaml.dump(content, fh, default_flow_style=False)

    docker_compose_path.write_text(_escape_cpus(docker_compose_path.read_text()))
