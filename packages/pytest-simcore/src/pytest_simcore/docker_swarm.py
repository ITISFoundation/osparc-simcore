# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint: disable=too-many-branches

import asyncio
import json
import logging
import subprocess
from collections.abc import AsyncIterator, Awaitable, Callable, Iterable, Iterator
from contextlib import suppress
from datetime import timedelta
from pathlib import Path
from typing import Any, Final

import aiodocker
import docker
import docker.errors
import docker.models.networks
import pytest
import pytest_asyncio
import yaml
from common_library.dict_tools import copy_from_dict
from docker.errors import APIError
from faker import Faker
from filelock import FileLock
from tenacity import AsyncRetrying, Retrying, TryAgain, retry
from tenacity.before_sleep import before_sleep_log
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed, wait_random_exponential

from .docker_compose import _filter_services_and_dump
from .helpers import FIXTURE_CONFIG_CORE_SERVICES_SELECTION, FIXTURE_CONFIG_OPS_SERVICES_SELECTION
from .helpers.constants import HEADER_STR, MINUTE
from .helpers.host import get_localhost_ip
from .helpers.logging_tools import log_context
from .helpers.typing_env import EnvVarsDict
from .helpers.valkey_tools import get_valkey_databases_count, set_valkey_databases_count
from .helpers.xdist import (
    get_max_xdist_workers,
    get_xdist_root_tmp_path,
    is_xdist_controller,
    is_xdist_worker,
    read_shared_resources,
    record_shared_resource,
    run_once_across_workers,
)

_logger: logging.Logger = logging.getLogger(__name__)

_DOCKER_STACK_SETUP_TIMEOUT: Final[timedelta] = timedelta(minutes=8)
_DOCKER_SWARM_SETUP_TIMEOUT: Final[timedelta] = timedelta(minutes=2)


class _ResourceStillNotRemovedError(Exception):
    pass


def _is_docker_swarm_init(docker_client: docker.client.DockerClient) -> bool:
    try:
        docker_client.swarm.reload()
        inspect_result = docker_client.swarm.attrs
        assert isinstance(inspect_result, dict)
    except APIError:
        return False
    return True


@retry(
    wait=wait_fixed(1),
    stop=stop_after_delay(8 * MINUTE),
    before_sleep=before_sleep_log(_logger, logging.INFO),
    reraise=True,
)
def assert_service_is_running(service) -> None:
    """Checks that a number of tasks of this service are in running state"""

    def _get(obj: dict[str, Any], dotted_key: str, default=None) -> Any:
        keys = dotted_key.split(".")
        value = obj
        for key in keys[:-1]:
            value = value.get(key, {})
        return value.get(keys[-1], default)

    service_name = service.name
    num_replicas_specified = _get(service.attrs, "Spec.Mode.Replicated.Replicas", default=1)

    _logger.info(
        "Waiting for service_name='%s' to have num_replicas_specified=%s ...",
        service_name,
        num_replicas_specified,
    )

    tasks = list(service.tasks())
    assert tasks

    #
    # NOTE: We have noticed using the 'last updated' task is not necessarily
    # the most actual of the tasks. It depends e.g. on the restart policy.
    # We explored the possibility of determining success by using the condition
    # "DesiredState" == "Status.State" but realized that "DesiredState" is not
    # part of the specs but can be updated by the swarm at runtime.
    # Finally, the decision was to use the state 'running' understanding that
    # the swarms flags this state to the service when it is up and healthy.
    #
    # SEE https://docs.docker.com/engine/swarm/how-swarm-mode-works/swarm-task-states/

    tasks_current_state = [_get(task, "Status.State") for task in tasks]
    num_running = sum(current == "running" for current in tasks_current_state)

    assert num_running == num_replicas_specified, (
        f"service_name='{service_name}'  has tasks_current_state={tasks_current_state}, "
        f"but expected at least num_replicas_specified='{num_replicas_specified}' running"
    )

    _logger.info("%s is up and running!!", service_name)


def _fetch_and_print_services(docker_client: docker.client.DockerClient, extra_title: str) -> None:
    _logger.info(HEADER_STR.format(f"docker services running {extra_title}"))

    for service_obj in docker_client.services.list():
        tasks = {}
        service = {}
        with suppress(Exception):
            # trims dicts (more info in dumps)
            assert service_obj.attrs
            service = copy_from_dict(
                service_obj.attrs,
                include={
                    "ID": ...,
                    "CreatedAt": ...,
                    "UpdatedAt": ...,
                    "Spec": {"Name", "Labels", "Mode"},
                },
            )

            tasks = [
                copy_from_dict(
                    task,
                    include={
                        "ID": ...,
                        "CreatedAt": ...,
                        "UpdatedAt": ...,
                        "Spec": {"ContainerSpec": {"Image", "Labels", "Env"}},
                        "Status": ...,
                        "DesiredState": ...,
                        "ServiceID": ...,
                        "NodeID": ...,
                        "Slot": ...,
                    },
                )
                for task in service_obj.tasks()  # type: ignore
            ]

        _logger.info(HEADER_STR.format(service_obj.name))  # type: ignore
        _logger.debug(json.dumps({"service": service, "tasks": tasks}, indent=1))


@pytest.fixture(scope="session")
def docker_client() -> Iterator[docker.client.DockerClient]:
    client = docker.from_env()
    yield client
    client.close()


@retry(
    wait=wait_fixed(2),
    stop=stop_after_delay(15),
    reraise=True,
)
def _ensure_swarm_init(docker_client: docker.client.DockerClient) -> None:
    if not _is_docker_swarm_init(docker_client):
        with log_context(logging.INFO, "initializing docker swarm", logger=_logger):
            docker_client.swarm.init(advertise_addr=get_localhost_ip())

    # if still not in swarm, raise an error to try and initialize again
    assert _is_docker_swarm_init(docker_client)


def _leave_swarm(docker_client: docker.client.DockerClient) -> None:
    with log_context(logging.INFO, "leaving docker swarm", logger=_logger):
        assert docker_client.swarm.leave(force=True)


@pytest.fixture(scope="module")
def docker_swarm(
    docker_client: docker.client.DockerClient,
    keep_docker_up: bool,
    request: pytest.FixtureRequest,
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[None]:
    """inits docker swarm"""
    with run_once_across_workers(
        request, tmp_path_factory, "docker_swarm", timeout=_DOCKER_SWARM_SETUP_TIMEOUT
    ) as is_first:
        if is_first:
            _ensure_swarm_init(docker_client)
            record_shared_resource(request, tmp_path_factory, kind="swarm")

    yield

    if is_xdist_worker(request):
        return  # the xdist controller leaves the swarm at session end (see `pytest_sessionfinish`)

    if not keep_docker_up:
        _leave_swarm(docker_client)

    assert _is_docker_swarm_init(docker_client) is keep_docker_up


@retry(
    wait=wait_fixed(0.3),
    retry=retry_if_exception_type(AssertionError),
    stop=stop_after_delay(30),
)
def _wait_for_migration_service_to_be_removed(
    docker_client: docker.client.DockerClient,
) -> None:
    for service in docker_client.services.list():
        if "migration" in service.name:  # type: ignore
            raise TryAgain


def _force_remove_migration_service(docker_client: docker.client.DockerClient) -> None:
    for migration_service in (
        service
        for service in docker_client.services.list()
        if "migration" in service.name  # type: ignore
    ):
        _logger.warning(
            "migration service detected before updating stack, it will be force-removed now and re-deployed "
            "to ensure DB update"
        )
        migration_service.remove()  # type: ignore
        _wait_for_migration_service_to_be_removed(docker_client)
        _logger.info("forced updated %s", migration_service.name)  # type: ignore


def _deploy_stack(compose_file: Path, stack_name: str) -> None:
    for attempt in Retrying(
        stop=stop_after_delay(60),
        wait=wait_random_exponential(max=5),
        retry=retry_if_exception_type(TryAgain),
        reraise=True,
    ):
        with attempt:
            try:
                cmd = [
                    "docker",
                    "stack",
                    "deploy",
                    "--with-registry-auth",
                    "--compose-file",
                    f"{compose_file.name}",
                    f"{stack_name}",
                ]
                subprocess.run(  # noqa: S603
                    cmd,
                    check=True,
                    cwd=compose_file.parent,
                    capture_output=True,
                )
            except subprocess.CalledProcessError as err:
                if b"update out of sequence" in err.stderr:
                    raise TryAgain from err
                pytest.fail(
                    reason=(
                        f"deploying docker_stack failed: {err.cmd=}, {err.returncode=}, {err.stdout=}, {err.stderr=}"
                        "\nTIP: frequent failure is due to a corrupt .env file: Delete .env and .env.bak"
                    )
                )


def _make_dask_sidecar_certificates(simcore_service_folder: Path) -> None:
    dask_sidecar_root_folder = simcore_service_folder / "dask-sidecar"
    subprocess.run(
        ["make", "certificates"],  # noqa: S607
        cwd=dask_sidecar_root_folder,
        check=True,
        capture_output=True,
    )


def _create_network_if_missing(docker_client: docker.client.DockerClient, network_name: str) -> bool:
    """Returns True if the network had to be created"""
    try:
        docker_client.networks.get(network_name)
    except docker.errors.NotFound:
        docker_client.networks.create(
            name=network_name,
            driver="overlay",
            attachable=True,
            labels={
                "com.docker.stack.namespace": "simcore",
                "created_by": "pytest-simcore",
            },
        )
        return True
    return False


def _remove_network_when_free(docker_client: docker.client.DockerClient, network_name: str) -> None:
    """Removes `network_name`, retrying while swarm tasks still have endpoints attached to it
    (endpoint draining after `docker stack remove` is asynchronous on the daemon)
    """
    with suppress(docker.errors.NotFound):
        network = docker_client.networks.get(network_name)
        for attempt in Retrying(
            stop=stop_after_delay(3 * MINUTE),
            wait=wait_fixed(2),
            retry=retry_if_exception_type(APIError),
            before_sleep=before_sleep_log(_logger, logging.INFO),
            reraise=True,
        ):
            with attempt:
                network.remove()


def _stack_network(
    network_name: str,
    docker_client: docker.client.DockerClient,
    keep_docker_up: bool,
    request: pytest.FixtureRequest,
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[docker.models.networks.Network]:
    created_new = False
    with run_once_across_workers(
        request, tmp_path_factory, f"docker_network_{network_name}", timeout=_DOCKER_SWARM_SETUP_TIMEOUT
    ) as is_first:
        if is_first:
            created_new = _create_network_if_missing(docker_client, network_name)
            if created_new:
                record_shared_resource(request, tmp_path_factory, kind="network", name=network_name)

    yield docker_client.networks.get(network_name)

    # under xdist the controller removes it at session end (see `pytest_sessionfinish`)
    if created_new and not keep_docker_up and not is_xdist_worker(request):
        _remove_network_when_free(docker_client, network_name)


@pytest.fixture(scope="module")
def simcore_docker_network(
    docker_swarm: None,
    docker_client: docker.client.DockerClient,
    simcore_docker_compose: dict,
    keep_docker_up,
    request: pytest.FixtureRequest,
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[docker.models.networks.Network]:
    # get network name from docker-compose
    network_name = simcore_docker_compose["networks"]["default"]["name"]
    yield from _stack_network(network_name, docker_client, keep_docker_up, request, tmp_path_factory)


@pytest.fixture(scope="module")
def interactive_services_subnet_docker_network(
    docker_swarm: None,
    docker_client: docker.client.DockerClient,
    simcore_docker_compose: dict,
    keep_docker_up: bool,
    request: pytest.FixtureRequest,
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[docker.models.networks.Network]:
    # get network name from docker-compose
    network_name = simcore_docker_compose["networks"]["interactive_services_subnet"]["name"]
    yield from _stack_network(network_name, docker_client, keep_docker_up, request, tmp_path_factory)


def _remove_stacks(docker_client: docker.client.DockerClient, stack_names: Iterable[str]) -> None:
    """Removes the stacks in the given order and waits until the daemon drained their resources"""
    # WORKAROUND https://github.com/moby/moby/issues/30942#issue-207070098
    for stack in stack_names:
        try:
            subprocess.run(  # noqa: S603
                f"docker stack remove {stack}".split(" "),
                check=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError as err:
            _logger.warning(
                "Ignoring failure while executing '%s' (returned code %d):\n%s\n%s\n%s\n%s\n",
                err.cmd,
                err.returncode,
                HEADER_STR.format("stdout"),
                err.stdout.decode("utf8") if err.stdout else "",
                HEADER_STR.format("stderr"),
                err.stderr.decode("utf8") if err.stderr else "",
            )

        # The check order is intentional because some resources depend on others to be removed
        # e.g. cannot remove networks/volumes used by running containers
        for resource_name in ("services", "containers", "volumes", "networks"):
            resource_client = getattr(docker_client, resource_name)

            for attempt in Retrying(
                wait=wait_fixed(2),
                stop=stop_after_delay(3 * MINUTE),
                before_sleep=before_sleep_log(_logger, logging.INFO),
                reraise=True,
            ):
                with attempt:
                    pending = resource_client.list(filters={"label": f"com.docker.stack.namespace={stack}"})
                    if pending:
                        if resource_name in ("volumes",):
                            # WARNING: rm volumes on this stack might be a problem when shared
                            # between different stacks
                            # NOTE: volumes are removed to avoid mixing configs (e.g. postgres db credentials)
                            for resource in pending:
                                resource.remove(force=True)

                        msg = f"Waiting for {len(pending)} {resource_name} to shutdown: {pending}."
                        raise _ResourceStillNotRemovedError(msg)

    _fetch_and_print_services(docker_client, "[AFTER REMOVED]")


def pytest_sessionfinish(session: pytest.Session) -> None:
    """Under xdist, workers leave the shared docker resources up: the controller removes them here"""
    if not is_xdist_controller(session.config) or session.config.getoption("--keep-docker-up", default=False):
        return

    resources = read_shared_resources(session.config)
    if not resources:
        return

    docker_client = docker.from_env()
    try:
        # stacks first, in reverse deploy order since they share networks
        _remove_stacks(docker_client, [r["name"] for r in reversed(resources) if r["kind"] == "stack"])
        for network in (r["name"] for r in resources if r["kind"] == "network"):
            _remove_network_when_free(docker_client, network)
        if any(r["kind"] == "swarm" for r in resources):
            _leave_swarm(docker_client)
    finally:
        docker_client.close()


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def docker_stack(  # noqa: C901
    osparc_simcore_services_dir: Path,
    simcore_docker_network: docker.models.networks.Network,
    interactive_services_subnet_docker_network: docker.models.networks.Network,
    docker_client: docker.client.DockerClient,
    core_docker_compose_file: Path,
    ops_docker_compose_file: Path,
    simcore_docker_compose: dict,
    ops_docker_compose: dict,
    keep_docker_up: bool,
    env_vars_for_docker_compose: EnvVarsDict,
    request: pytest.FixtureRequest,
    tmp_path_factory: pytest.TempPathFactory,
) -> AsyncIterator[dict]:
    """deploys core and ops stacks and returns as soon as all are running

    Under xdist, the first worker deploys the stacks for the whole run and the controller removes them.
    """

    # WARNING: keep prefix "pytest-" in stack names
    core_stack_name = env_vars_for_docker_compose["SWARM_STACK_NAME"]
    ops_stack_name = "pytest-ops"

    assert core_stack_name
    assert core_stack_name.startswith("pytest-")

    def _collected_services_union(attr_name: str) -> list[str]:
        # NOTE: collection completes before any test runs, so `session.items` already lists
        # every test this run will execute (the full suite, or a `-k`-filtered subset)
        seen: set[str] = set()
        union: list[str] = []
        for item in request.session.items:
            for name in getattr(item.module, attr_name, []):
                if name not in seen:
                    seen.add(name)
                    union.append(name)
        return union

    def _widen_valkey_databases(compose_path: Path) -> None:
        # `--databases` is a boot-time argument: reserve one bank of logical databases per potential
        # xdist worker (+1 for the master) in the compose BEFORE deploying
        content = yaml.safe_load(compose_path.read_text())
        base_count = get_valkey_databases_count(content)
        if base_count is None:
            return
        set_valkey_databases_count(content, (get_max_xdist_workers(request.config) + 1) * base_count)
        compose_path.write_text(yaml.dump(content, default_flow_style=False))

    def _compose_file_for(unfiltered: dict, filtered_path: Path, label: str, selection_attr: str) -> Path:
        if not is_xdist_worker(request):
            return filtered_path
        # only the first worker deploys, so it must deploy the UNION of the services selected by all
        # collected modules (the unfiltered compose has services without test images)
        union_path = get_xdist_root_tmp_path(tmp_path_factory) / f"{label}_union_docker_compose.yml"
        with FileLock(f"{union_path}.lock"):
            # atomic rename: another worker must never read a half-written compose
            if not union_path.exists():
                tmp_path = union_path.with_name(f"{union_path.name}.tmp")
                _filter_services_and_dump(_collected_services_union(selection_attr), unfiltered, tmp_path)
                _widen_valkey_databases(tmp_path)
                tmp_path.replace(union_path)  # atomic on the same filesystem
        return union_path

    stacks = [
        (
            "ops",
            ops_stack_name,
            _compose_file_for(
                ops_docker_compose, ops_docker_compose_file, "ops", FIXTURE_CONFIG_OPS_SERVICES_SELECTION
            ),
        ),
        (
            "core",
            core_stack_name,
            _compose_file_for(
                simcore_docker_compose, core_docker_compose_file, "core", FIXTURE_CONFIG_CORE_SERVICES_SELECTION
            ),
        ),
    ]

    # All SELECTED services ready
    # - notice that the timeout is set for all services in both stacks
    # - TODO: the time to deploy will depend on the number of services selected
    async def _check_all_services_are_running():
        # NOTE: only THIS stack's services: under xdist, services other workers' tests create and
        # remove concurrently would make `assert_service_is_running` fail on already-gone services
        stack_services = [
            service
            for _, stack_name, _ in stacks
            for service in docker_client.services.list(filters={"label": f"com.docker.stack.namespace={stack_name}"})
        ]
        done, pending = await asyncio.wait(
            [
                asyncio.get_event_loop().run_in_executor(None, assert_service_is_running, service)
                for service in stack_services
            ],
            return_when=asyncio.FIRST_EXCEPTION,
        )
        assert done, f"no services ready, they all failed! [{pending}]"

        for future in done:
            if exc := future.exception():
                raise exc

        assert not pending, f"some service did not start correctly [{pending}]"

    with run_once_across_workers(
        request, tmp_path_factory, "docker_stack", timeout=_DOCKER_STACK_SETUP_TIMEOUT
    ) as is_first:
        if is_first:
            # recorded BEFORE deploying so the controller also cleans up a half-deployed stack
            for _, stack_name, _ in stacks:
                record_shared_resource(request, tmp_path_factory, kind="stack", name=stack_name)

            # NOTE: if the migration service was already running prior to this call it must
            # be force updated so that it does its job. else it remains and tests will fail
            _force_remove_migration_service(docker_client)
            _make_dask_sidecar_certificates(osparc_simcore_services_dir)
            # make up-version
            for _, stack_name, compose_file in stacks:
                _deploy_stack(compose_file, stack_name)

            try:
                await _check_all_services_are_running()
            finally:
                _fetch_and_print_services(docker_client, "[BEFORE TEST]")

    yield {
        "stacks": {
            key: {"name": stack_name, "compose": yaml.safe_load(compose_file.read_text())}
            for key, stack_name, compose_file in stacks
        },
        "services": [service.name for service in docker_client.services.list()],  # type: ignore
    }

    # TEAR DOWN ----------------------

    if is_xdist_worker(request):
        return  # the xdist controller removes the stacks at session end (see `pytest_sessionfinish`)

    _fetch_and_print_services(docker_client, "[AFTER TEST]")

    if keep_docker_up:
        # skip bringing the stack down
        return

    # NOTE: remove them in reverse order since stacks share common networks
    _remove_stacks(docker_client, [stack_name for _, stack_name, _ in reversed(stacks)])


@pytest.fixture
async def docker_network(
    docker_swarm: None,
    async_docker_client: aiodocker.Docker,
    faker: Faker,
) -> AsyncIterator[Callable[..., Awaitable[dict[str, Any]]]]:
    networks = []

    async def _network_creator(**network_config_kwargs) -> dict[str, Any]:
        network = await async_docker_client.networks.create(
            config={"Name": faker.uuid4(), "Driver": "overlay"} | network_config_kwargs
        )
        assert network
        _logger.info("created network %s", network)
        networks.append(network)
        return await network.show()

    yield _network_creator

    # wait until all networks are really gone
    async def _wait_for_network_deletion(network: aiodocker.docker.DockerNetwork):
        network_name = (await network.show())["Name"]
        await network.delete()
        async for attempt in AsyncRetrying(reraise=True, wait=wait_fixed(1), stop=stop_after_delay(60)):
            with attempt:
                _logger.info("waiting for network '%s' deletion...", network_name)
                list_of_network_names = [n["Name"] for n in await async_docker_client.networks.list()]
                assert network_name not in list_of_network_names
        _logger.info("network '%s' deleted", network_name)

    with log_context(logging.INFO, "removing all networks", logger=_logger):
        await asyncio.gather(*[_wait_for_network_deletion(network) for network in networks])
