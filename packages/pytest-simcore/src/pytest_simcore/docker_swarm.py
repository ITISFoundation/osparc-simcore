# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint: disable=too-many-branches

import asyncio
import json
import logging
import subprocess
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from contextlib import suppress
from datetime import timedelta
from pathlib import Path
from typing import Any, Final
from uuid import uuid4

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
    SharedResourceRegistry,
    get_max_xdist_workers,
    get_worker_id,
    get_xdist_root_tmp_path,
    is_xdist_worker,
)

_logger: logging.Logger = logging.getLogger(__name__)

_DOCKER_STACK_REGISTRY_NAME: Final[str] = "docker_stack"
_DOCKER_SWARM_REGISTRY_NAME: Final[str] = "docker_swarm"
_DOCKER_STACK_READY_TIMEOUT: Final[timedelta] = timedelta(minutes=8)


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

    print(f"--> {service_name} is up and running!!")


def _fetch_and_print_services(docker_client: docker.client.DockerClient, extra_title: str) -> None:
    print(HEADER_STR.format(f"docker services running {extra_title}"))

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

        print(HEADER_STR.format(service_obj.name))  # type: ignore
        print(json.dumps({"service": service, "tasks": tasks}, indent=1))


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


@pytest.fixture(scope="module")
def docker_swarm(
    docker_client: docker.client.DockerClient,
    keep_docker_up: bool,
    request: pytest.FixtureRequest,
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[None]:
    """inits docker swarm

    The swarm is a daemon-wide resource shared by every xdist worker: under xdist it is
    ref-counted via `SharedResourceRegistry` so the first holder initializes it and ONLY the
    last holder leaves it (a module-scoped `swarm.leave` in one worker would otherwise strip
    swarm-manager state from the daemon while other workers are still running, making their
    docker API calls fail with 503 "this node is not a swarm manager").
    """
    registry: SharedResourceRegistry | None = (
        SharedResourceRegistry(get_xdist_root_tmp_path(tmp_path_factory), _DOCKER_SWARM_REGISTRY_NAME)
        if is_xdist_worker(request)
        else None
    )
    token = f"{get_worker_id(request)}-{uuid4().hex}"
    if registry is None:
        _ensure_swarm_init(docker_client)
    elif registry.register(token):
        try:
            _ensure_swarm_init(docker_client)
        except BaseException:
            registry.mark_failed()
            registry.unregister(token)
            raise
        registry.mark_ready()
    else:
        registry.wait_ready(timeout=timedelta(minutes=2))

    yield

    if registry is not None and not registry.unregister(token):
        # other workers still use the swarm
        return

    if not keep_docker_up:
        print("<-- leaving docker swarm...")
        assert docker_client.swarm.leave(force=True)
        print("<-- docker swarm left.")

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
        print(
            "WARNING: migration service detected before updating stack, it will be force-removed now and re-deployed "
            "to ensure DB update"
        )
        migration_service.remove()  # type: ignore
        _wait_for_migration_service_to_be_removed(docker_client)
        print(f"forced updated {migration_service.name}.")  # type: ignore


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


def _create_stack_network(
    docker_client: docker.client.DockerClient, network_name: str
) -> docker.models.networks.Network:
    return docker_client.networks.create(
        name=network_name,
        driver="overlay",
        attachable=True,
        labels={
            "com.docker.stack.namespace": "simcore",
            "created_by": "pytest-simcore",
        },
    )


def _get_or_create_network(
    docker_client: docker.client.DockerClient, network_name: str
) -> tuple[docker.models.networks.Network, bool]:
    """Returns (network, created_new).

    Safe across xdist workers: two workers can both observe `NotFound` and race to create
    the network; the loser gets a 409 Conflict and must fetch what the winner created.
    """
    try:
        return docker_client.networks.get(network_name), False
    except docker.errors.NotFound:
        pass
    try:
        return _create_stack_network(docker_client, network_name), True
    except APIError as err:
        if err.response is None or err.response.status_code != 409:
            raise
        # another worker is creating it right now: wait for it to show up
        for attempt in Retrying(
            stop=stop_after_delay(2 * MINUTE),
            wait=wait_fixed(0.2),
            retry=retry_if_exception_type(docker.errors.NotFound),
            reraise=True,
        ):
            with attempt:
                network = docker_client.networks.get(network_name)
        return network, False


_CREATED_STACK_NETWORKS_MARKER_NAME: Final[str] = "created_stack_networks.txt"


def _record_created_network_for_shared_cleanup(root_tmp_path: Path, network_name: str) -> None:
    """Appends `network_name` to the list of networks created during this xdist session, so the
    last `docker_stack` user removes them once no worker has services attached anymore (see
    `simcore_docker_network`): winning the create race does NOT grant lifetime ownership.
    """
    marker = root_tmp_path / _CREATED_STACK_NETWORKS_MARKER_NAME
    with FileLock(f"{marker}.lock"), marker.open("a", encoding="utf8") as fd:
        fd.write(f"{network_name}\n")


def _take_created_networks_for_shared_cleanup(root_tmp_path: Path) -> list[str]:
    """Returns (and clears) the networks recorded via `_record_created_network_for_shared_cleanup`"""
    marker = root_tmp_path / _CREATED_STACK_NETWORKS_MARKER_NAME
    with FileLock(f"{marker}.lock"):
        if not marker.exists():
            return []
        names = [line.strip() for line in marker.read_text(encoding="utf8").splitlines() if line.strip()]
        marker.unlink(missing_ok=True)
    return names


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
    network, created_new = _get_or_create_network(docker_client, network_name)
    if created_new and not keep_docker_up and is_xdist_worker(request):
        _record_created_network_for_shared_cleanup(get_xdist_root_tmp_path(tmp_path_factory), network_name)

    yield network

    if created_new and not keep_docker_up and not is_xdist_worker(request):
        with suppress(docker.errors.NotFound):
            network.remove()


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
    network, created_new = _get_or_create_network(docker_client, network_name)
    if created_new and not keep_docker_up and is_xdist_worker(request):
        _record_created_network_for_shared_cleanup(get_xdist_root_tmp_path(tmp_path_factory), network_name)

    yield network

    if created_new and not keep_docker_up and not is_xdist_worker(request):
        with suppress(docker.errors.NotFound):
            network.remove()


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def docker_stack(  # noqa: C901, PLR0915
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

    Under pytest-xdist, every worker process runs this fixture independently, but the
    underlying stack is a single shared resource: callers coordinate via a cross-process
    reference-counted registry (see `SharedResourceRegistry`) so exactly one worker deploys
    it and only the last caller tears it down, regardless of how many workers/modules use it.
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
        # valkey/redis `--databases` is a BOOT-TIME argument (NOT CONFIG SET-able), so the widened
        # count must be baked into the compose BEFORE deploy: reserve one bank of logical
        # databases per potential xdist worker (+1 bank for the master/default one) on the shared
        # container, read from the base count the compose itself declares (never hardcoded here)
        content = yaml.safe_load(compose_path.read_text())
        base_count = get_valkey_databases_count(content)
        if base_count is None:
            return
        set_valkey_databases_count(content, (get_max_xdist_workers(request.config) + 1) * base_count)
        compose_path.write_text(yaml.dump(content, default_flow_style=False))

    def _compose_file_for(unfiltered: dict, filtered_path: Path, label: str, selection_attr: str) -> Path:
        if not is_xdist_worker(request):
            # single-process run: unaffected, same per-module filtered selection as before
            return filtered_path
        # NOTE: under xdist, different test modules may declare different (smaller)
        # `core_services_selection`/`ops_services_selection` subsets, but only the FIRST
        # module to reach this fixture actually deploys (see `owns_stack` below) - deploying
        # ITS OWN filtered subset would starve later modules of services they need (e.g. a
        # module selecting only "postgres" would prevent "rabbit"/"redis" from ever being
        # deployed for other modules). Deploy the UNION of every collected module's selection
        # instead, so every module's selection is always already satisfied - deploying the
        # full, unfiltered compose is NOT an option: it includes production services whose
        # images aren't built/available in a test environment.
        union_path = get_xdist_root_tmp_path(tmp_path_factory) / f"{label}_union_docker_compose.yml"
        with FileLock(f"{union_path}.lock"):
            # NOTE: the check+dump must happen under a cross-process lock and the file must
            # appear atomically (write to .tmp + atomic rename): a worker deploying the stack
            # must never read a half-written compose produced concurrently by another worker
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

    registry: SharedResourceRegistry | None = (
        SharedResourceRegistry(get_xdist_root_tmp_path(tmp_path_factory), _DOCKER_STACK_REGISTRY_NAME)
        if is_xdist_worker(request)
        else None
    )
    token = f"{get_worker_id(request)}-{uuid4().hex}"
    owns_stack = True if registry is None else registry.register(token)

    def _teardown_shared_resources() -> None:  # noqa: C901
        """removes the deployed stacks and the shared networks recorded for this session.

        Callers must hold last-owner teardown rights (normal teardown, or the setup-failure
        path below when no stack users remain); `keep_docker_up` short-circuits it.
        """
        _fetch_and_print_services(docker_client, "[AFTER TEST]")

        if keep_docker_up:
            # skip bringing the stack down
            return

        # clean up. Guarantees that all services are down before creating a new stack!
        # WORKAROUND https://github.com/moby/moby/issues/30942#issue-207070098
        # (poll until the daemon finished draining stack resources before proceeding)

        # make down
        # NOTE: remove them in reverse order since stacks share common networks

        stacks.reverse()
        for _, stack, _ in stacks:
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

            # Waits that all resources get removed or force them
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

        # the shared networks are declared `external` in the composes, so `docker stack remove` does
        # NOT touch them: the network fixtures deliberately hand their removal to THIS last-owner
        # teardown (only the worker removing the last stack reference gets here), since the worker
        # that created a network may finish its modules while others still run services on it.
        # NOTE: xdist only — a non-xdist run removes them in its own network fixture teardowns and
        # must NOT read the marker (it could pick up leftovers of a crashed xdist session)
        if registry is not None:
            for network_name in _take_created_networks_for_shared_cleanup(get_xdist_root_tmp_path(tmp_path_factory)):
                try:
                    _remove_network_when_free(docker_client, network_name)
                except APIError:
                    _logger.warning(
                        "could not remove shared network '%s' after the last stack teardown: if no other "
                        "test session is running, remove it manually with 'docker network rm %s'",
                        network_name,
                        network_name,
                        exc_info=True,
                    )

        _fetch_and_print_services(docker_client, "[AFTER REMOVED]")

    stacks_deployed: dict[str, dict] = {}
    if owns_stack:
        try:
            # NOTE: if the migration service was already running prior to this call it must
            # be force updated so that it does its job. else it remains and tests will fail
            _force_remove_migration_service(docker_client)
            _make_dask_sidecar_certificates(osparc_simcore_services_dir)
            # make up-version
            for key, stack_name, compose_file in stacks:
                _deploy_stack(compose_file, stack_name)

                stacks_deployed[key] = {
                    "name": stack_name,
                    "compose": yaml.safe_load(compose_file.read_text()),
                }

            # All SELECTED services ready
            # - notice that the timeout is set for all services in both stacks
            # - TODO: the time to deploy will depend on the number of services selected
            async def _check_all_services_are_running():
                # NOTE: scoped to THIS stack's namespaces on purpose: under xdist, other workers
                # may be concurrently creating/removing their own test services, and asserting
                # those (soon-gone, hence 404-forever) services here would stall the deploy until
                # `assert_service_is_running` times out and fails the whole shared stack
                stack_services = [
                    service
                    for _, stack_name, _ in stacks
                    for service in docker_client.services.list(
                        filters={"label": f"com.docker.stack.namespace={stack_name}"}
                    )
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
                        raise exc  # noqa: TRY301

                assert not pending, f"some service did not start correctly [{pending}]"

            try:
                await _check_all_services_are_running()
            finally:
                _fetch_and_print_services(docker_client, "[BEFORE TEST]")
        except BaseException:
            # the other workers would wait for a stack that will NEVER become ready: signal
            # them to fail fast and give up ownership, so the deploy is retried elsewhere
            if registry is not None:
                registry.mark_failed()
                if registry.unregister(token):
                    # last stack user and THIS fixture's post-yield teardown will never run
                    # (setup raised before yielding): tear down here, best-effort, so a failed
                    # deploy does not leave a half-deployed stack or the recorded shared
                    # networks behind for later sessions to trip over
                    try:
                        _teardown_shared_resources()
                    except Exception:
                        _logger.warning("best-effort teardown after failed deploy did not complete", exc_info=True)
            raise

        if registry is not None:
            registry.mark_ready()
    else:
        # another worker owns the deploy: wait until it signals the stack is ready (or failed)
        assert registry is not None
        registry.wait_ready(timeout=_DOCKER_STACK_READY_TIMEOUT)

        stacks_deployed = {
            key: {"name": stack_name, "compose": yaml.safe_load(compose_file.read_text())}
            for key, stack_name, compose_file in stacks
        }

    yield {
        "stacks": stacks_deployed,
        "services": [service.name for service in docker_client.services.list()],  # type: ignore
    }

    # TEAR DOWN ----------------------

    if registry is not None and not registry.unregister(token):
        # other workers/modules still use the shared stack
        return

    _teardown_shared_resources()


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
        print(f"--> created network {network=}")
        networks.append(network)
        return await network.show()

    yield _network_creator

    # wait until all networks are really gone
    async def _wait_for_network_deletion(network: aiodocker.docker.DockerNetwork):
        network_name = (await network.show())["Name"]
        await network.delete()
        async for attempt in AsyncRetrying(reraise=True, wait=wait_fixed(1), stop=stop_after_delay(60)):
            with attempt:
                print(f"<-- waiting for network '{network_name}' deletion...")
                list_of_network_names = [n["Name"] for n in await async_docker_client.networks.list()]
                assert network_name not in list_of_network_names
            print(f"<-- network '{network_name}' deleted")

    print(f"<-- removing all networks {networks=}")
    await asyncio.gather(*[_wait_for_network_deletion(network) for network in networks])
