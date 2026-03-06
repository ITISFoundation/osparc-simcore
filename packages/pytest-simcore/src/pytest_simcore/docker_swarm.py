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
from copy import deepcopy
from pathlib import Path
from typing import Any

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
from tenacity import AsyncRetrying, Retrying, TryAgain, retry
from tenacity.before_sleep import before_sleep_log
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed, wait_random_exponential

from .helpers.constants import HEADER_STR, MINUTE
from .helpers.host import get_localhost_ip
from .helpers.typing_env import EnvVarsDict

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Phased deployment order (mirrors Makefile deploy batches)
# ---------------------------------------------------------------------------


def _get_compose_service_order() -> list[str]:
    docker_compose_path = Path(__file__).parent.parent.parent.parent.parent / "services" / "docker-compose.yml"
    data = yaml.safe_load(docker_compose_path.read_text())
    return list(data["services"].keys())


#: Maximum number of app services being started (not yet running) at any time.
_MAX_CONCURRENT_SERVICE_STARTS: int = 4


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


@pytest.fixture(scope="module")
def docker_swarm(docker_client: docker.client.DockerClient, keep_docker_up: bool) -> Iterator[None]:
    """inits docker swarm"""

    for attempt in Retrying(wait=wait_fixed(2), stop=stop_after_delay(15), reraise=True):
        with attempt:
            if not _is_docker_swarm_init(docker_client):
                print("--> initializing docker swarm...")
                docker_client.swarm.init(advertise_addr=get_localhost_ip())
                print("--> docker swarm initialized.")

            # if still not in swarm, raise an error to try and initialize again
            assert _is_docker_swarm_init(docker_client)

    yield

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


# ---------------------------------------------------------------------------
# Phased (batched) core-stack deployment helpers
# ---------------------------------------------------------------------------


async def _async_assert_service_is_running(
    async_docker: aiodocker.Docker,
    service_name: str,
    stack_name: str,
) -> None:
    """Check that a swarm service has the expected number of running tasks."""
    full_service_name = f"{stack_name}_{service_name}"

    async for attempt in AsyncRetrying(wait=wait_fixed(0.2), stop=stop_after_delay(8 * MINUTE), reraise=True):
        with attempt:
            # Fetch tasks for this service, filtered by desired running state
            tasks = list(
                await async_docker.tasks.list(
                    filters={
                        "service": full_service_name,
                        "desired-state": "running",
                    }
                )
            )

            # Determine requested replicas from service spec
            services = await async_docker.services.list(filters={"name": full_service_name})
            assert services, f"Service '{full_service_name}' not found in swarm"
            svc_spec = services[0].get("Spec", {})
            num_replicas = svc_spec.get("Mode", {}).get("Replicated", {}).get("Replicas", 1)

            num_running = sum(1 for t in tasks if t.get("Status", {}).get("State") == "running")

            assert num_running >= num_replicas, f"'{full_service_name}' has {num_running}/{num_replicas} running tasks"
            _logger.info("--> %s is up and running!", full_service_name)


async def _is_service_already_running(
    async_docker: aiodocker.Docker,
    service_name: str,
    stack_name: str,
) -> bool:
    """Single-shot check whether a service already has all replicas running."""
    full_service_name = f"{stack_name}_{service_name}"

    services = await async_docker.services.list(filters={"name": full_service_name})
    if not services:
        return False

    svc_spec = services[0].get("Spec", {})
    num_replicas = svc_spec.get("Mode", {}).get("Replicated", {}).get("Replicas", 1)

    tasks = list(
        await async_docker.tasks.list(
            filters={
                "service": full_service_name,
                "desired-state": "running",
            }
        )
    )
    num_running = sum(1 for t in tasks if t.get("Status", {}).get("State") == "running")
    return num_running >= num_replicas


async def _filter_already_running(
    async_docker: aiodocker.Docker,
    service_names: list[str],
    stack_name: str,
) -> list[str]:
    """Return only the services from *service_names* that are NOT yet running."""
    if not service_names:
        return []

    results = await asyncio.gather(
        *(_is_service_already_running(async_docker, name, stack_name) for name in service_names)
    )
    not_running = [name for name, is_running in zip(service_names, results, strict=True) if not is_running]
    if already := len(service_names) - len(not_running):
        _logger.info(
            "Skipping %d service(s) already running: %s",
            already,
            [n for n, r in zip(service_names, results, strict=True) if r],
        )
    return not_running


async def _wait_for_services_running(
    async_docker: aiodocker.Docker,
    service_names: list[str],
    stack_name: str,
) -> None:
    """Wait for every service in *service_names* to be running (parallel)."""
    if not service_names:
        return
    _logger.info(
        "Waiting for %d service(s) to become ready: %s",
        len(service_names),
        service_names,
    )
    await asyncio.gather(*(_async_assert_service_is_running(async_docker, name, stack_name) for name in service_names))


def _compute_deployment_order(
    selected_services: set[str],
) -> list[str]:
    """Return an ordered flat list of services to deploy, filtered to *selected_services*.

    Services appear in the predefined order.  Any selected service not
    present in the predefined list is appended at the end so nothing is
    missed.
    """
    ordered: list[str] = [name for name in _get_compose_service_order() if name in selected_services]

    # Catch-all - services in the selection but not in the predefined list
    ordered.extend(sorted(selected_services - set(ordered)))

    return ordered


def _get_target_replicas(full_compose: dict, service_name: str) -> int:
    """Return the target replica count for *service_name* from the compose dict."""
    svc = full_compose.get("services", {}).get(service_name, {})
    return svc.get("deploy", {}).get("replicas", 1)


async def _scale_service(full_service_name: str, replicas: int) -> None:
    """Scale a Docker Swarm service to *replicas* tasks."""
    proc = await asyncio.create_subprocess_exec(
        "docker",
        "service",
        "scale",
        "--detach",
        f"{full_service_name}={replicas}",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        msg = f"docker service scale failed (rc={proc.returncode}): stdout={stdout.decode()}, stderr={stderr.decode()}"
        raise RuntimeError(msg)


#: Polling interval for the scaling loop (seconds).
_SCALE_POLL_INTERVAL: float = 0.5


async def _scale_app_services_in_order(
    async_docker: aiodocker.Docker,
    app_to_start: list[str],
    stack_name: str,
    full_compose: dict,
) -> None:
    """Scale app services strictly in the order given by *app_to_start*.

    Maintains an ordered status tracker where each service transitions
    through ``pending`` -> ``scaling`` -> ``ready``.  A fast polling loop
    picks up the next pending service as soon as a slot frees up.

    Global services (``deploy.mode: global``) cannot be scaled via
    ``docker service scale``; they already started from the initial
    zero-replicas deploy so we just wait for them to become ready.
    """

    _logger.info("Services will be started in this exact order: %s", app_to_start)

    # Ordered status tracker - preserves the order of app_to_start
    status: dict[str, str] = dict.fromkeys(app_to_start, "pending")

    # Index of the next service to scale (always moves forward)
    next_to_scale = 0

    while any(s != "ready" for s in status.values()):
        # --- 1. Check which "scaling" services have become ready ----------
        for name, state in status.items():
            if state != "scaling":
                continue
            if await _is_service_already_running(async_docker, name, stack_name):
                status[name] = "ready"
                _logger.info("--> %s is ready", name)

        # --- 2. Count how many are currently scaling ----------------------
        currently_scaling = sum(1 for s in status.values() if s == "scaling")

        # --- 3. Fill free slots with the next pending services in order ---
        while currently_scaling < _MAX_CONCURRENT_SERVICE_STARTS and next_to_scale < len(app_to_start):
            name = app_to_start[next_to_scale]
            next_to_scale += 1

            svc_def = full_compose.get("services", {}).get(name, {})
            is_global = svc_def.get("deploy", {}).get("mode") == "global"

            if is_global:
                # Global services cannot be scaled.  They were started by
                # the initial deploy and are tracked until ready.
                _logger.info(
                    "Tracking global service %s (already started, waiting for ready)",
                    name,
                )
            else:
                full_name = f"{stack_name}_{name}"
                target_replicas = _get_target_replicas(full_compose, name)
                _logger.info("Scaling %s to %d replica(s)", full_name, target_replicas)
                await _scale_service(full_name, target_replicas)

            status[name] = "scaling"
            currently_scaling += 1

        # --- 4. If anything is still not ready, wait before polling again -
        if any(s != "ready" for s in status.values()):
            await asyncio.sleep(_SCALE_POLL_INTERVAL)

    _logger.info("All %d app services are ready", len(app_to_start))


async def _deploy_core_stack_phased(
    compose_file: Path,
    stack_name: str,
    full_compose: dict,
    selected_services: set[str],
    *,
    keep_docker_up: bool,
) -> None:
    """Deploy the core stack in phases to reduce CI pressure.

    1. Deploy with **all services at replicas=0**.  This creates all
       services and networks in Docker Swarm without starting any
       containers — no image pulls, no task scheduling.
    2. Restore the original replica count service-by-service in the
       predefined deploy order.  A sliding window caps concurrent
       starts to ``_MAX_CONCURRENT_SERVICE_STARTS``.  As soon as one
       service becomes running, its slot is freed and the next service
       is scaled up immediately.

    When *keep_docker_up* is ``True`` the function first checks whether
    **all** expected services are already running.  If they are, it
    returns immediately without redeploying anything.  If only a few
    are missing, it deploys the original compose (no spec changes for
    running services) and waits for the missing ones.
    """
    deploy_order = _compute_deployment_order(selected_services)
    if not deploy_order:
        return

    async with aiodocker.Docker() as async_docker:
        # Skip services that are already running (e.g. --keep-docker-up)
        services_to_start = await _filter_already_running(async_docker, deploy_order, stack_name)

        if not services_to_start:
            _logger.info("All services already running, deploying full compose for consistency")
            _deploy_stack(compose_file, stack_name)
            return

        # Build explicit sets: services that need starting vs already running
        to_start_set = set(services_to_start)
        already_running_set = set(deploy_order) - to_start_set
        to_start = [s for s in deploy_order if s in to_start_set]

        # Step 1: Deploy all services at replicas=0 (only for services
        # that need starting).  When keep_docker_up is True, services
        # that are already running keep their original replica count so
        # they are not accidentally scaled down to 0.
        zero_compose = deepcopy(full_compose)
        for svc_name, svc_def in zero_compose.get("services", {}).items():
            deploy_cfg = svc_def.get("deploy", {})
            if deploy_cfg.get("mode", "replicated") == "replicated":
                if svc_name in to_start_set:
                    # Service needs starting — deploy at 0 replicas first
                    svc_def.setdefault("deploy", {})["replicas"] = 0
                elif keep_docker_up and svc_name in already_running_set:
                    # Service was confirmed running by _filter_already_running
                    # — preserve its original replica count so the deploy
                    # does not disrupt it.
                    _logger.info(
                        "Preserving replicas for already-running service %s",
                        svc_name,
                    )

        zero_file = compose_file.parent / ".phased-zero-replicas.yml"
        try:
            with zero_file.open("w") as fh:
                yaml.dump(zero_compose, fh, default_flow_style=False)
            _logger.info(
                "Deploying compose with %d service(s) at 0 replicas (keeping %d already-running service(s) intact)",
                len(to_start),
                len(deploy_order) - len(to_start),
            )
            _deploy_stack(zero_file, stack_name)
        finally:
            zero_file.unlink(missing_ok=True)

        # Step 2: Scale up services in the predefined deploy order.
        # A sliding-window tracker caps the number of concurrently-starting
        # services to _MAX_CONCURRENT_SERVICE_STARTS.  As soon as one
        # service becomes running, its slot is freed and the next service
        # in order is scaled immediately.
        _logger.info(
            "Scaling up %d service(s) (max %d concurrent): %s",
            len(to_start),
            _MAX_CONCURRENT_SERVICE_STARTS,
            to_start,
        )
        await _scale_app_services_in_order(
            async_docker=async_docker,
            app_to_start=to_start,
            stack_name=stack_name,
            full_compose=full_compose,
        )


@pytest.fixture(scope="module")
def simcore_docker_network(
    docker_swarm: None,
    docker_client: docker.client.DockerClient,
    simcore_docker_compose: dict,
    keep_docker_up,
) -> Iterator[docker.models.networks.Network]:
    # get network name from docker-compose
    network_name = simcore_docker_compose["networks"]["default"]["name"]
    created_new = False
    try:
        network = docker_client.networks.get(network_name)
    except docker.errors.NotFound:
        network = docker_client.networks.create(
            name=network_name,
            driver="overlay",
            attachable=True,
            labels={
                "com.docker.stack.namespace": "simcore",
                "created_by": "pytest-simcore",
            },
        )
        created_new = True

    yield network

    if created_new and not keep_docker_up:
        with suppress(docker.errors.NotFound):
            network.remove()


@pytest.fixture(scope="module")
def interactive_services_subnet_docker_network(
    docker_swarm: None,
    docker_client: docker.client.DockerClient,
    simcore_docker_compose: dict,
    keep_docker_up: bool,
) -> Iterator[docker.models.networks.Network]:
    # get network name from docker-compose
    network_name = simcore_docker_compose["networks"]["interactive_services_subnet"]["name"]
    created_new = False
    try:
        network = docker_client.networks.get(network_name)
    except docker.errors.NotFound:
        network = docker_client.networks.create(
            name=network_name,
            driver="overlay",
            attachable=True,
            labels={
                "com.docker.stack.namespace": "simcore",
                "created_by": "pytest-simcore",
            },
        )
        created_new = True
    yield network

    if created_new and not keep_docker_up:
        with suppress(docker.errors.NotFound):
            network.remove()


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def docker_stack(
    osparc_simcore_services_dir: Path,
    simcore_docker_network: docker.models.networks.Network,
    interactive_services_subnet_docker_network: docker.models.networks.Network,
    docker_client: docker.client.DockerClient,
    core_docker_compose_file: Path,
    ops_docker_compose_file: Path,
    keep_docker_up: bool,
    env_vars_for_docker_compose: EnvVarsDict,
) -> AsyncIterator[dict]:
    """deploys core and ops stacks and returns as soon as all are running"""

    # WARNING: keep prefix "pytest-" in stack names
    core_stack_name = env_vars_for_docker_compose["SWARM_STACK_NAME"]
    ops_stack_name = "pytest-ops"

    assert core_stack_name
    assert core_stack_name.startswith("pytest-")
    stacks = [
        (
            "ops",
            ops_stack_name,
            ops_docker_compose_file,
        ),
        (
            "core",
            core_stack_name,
            core_docker_compose_file,
        ),
    ]

    # NOTE: if the migration service was already running prior to this call it must
    # be force updated so that it does its job. else it remains and tests will fail
    _force_remove_migration_service(docker_client)
    _make_dask_sidecar_certificates(osparc_simcore_services_dir)

    # Deploy ops stack (single step - small stack)
    stacks_deployed: dict[str, dict] = {}
    _deploy_stack(ops_docker_compose_file, ops_stack_name)
    stacks_deployed["ops"] = {
        "name": ops_stack_name,
        "compose": yaml.safe_load(ops_docker_compose_file.read_text()),
    }

    # Deploy core stack in phases
    core_compose = yaml.safe_load(core_docker_compose_file.read_text())
    selected_services = set(core_compose.get("services", {}))

    try:
        await _deploy_core_stack_phased(
            compose_file=core_docker_compose_file,
            stack_name=core_stack_name,
            full_compose=core_compose,
            selected_services=selected_services,
            keep_docker_up=keep_docker_up,
        )

        stacks_deployed["core"] = {
            "name": core_stack_name,
            "compose": core_compose,
        }

        # Final check: ensure ops services are also ready
        async with aiodocker.Docker() as async_docker:
            ops_compose = stacks_deployed["ops"]["compose"]
            ops_service_names = list(ops_compose.get("services", {}))
            await _wait_for_services_running(async_docker, ops_service_names, ops_stack_name)

    finally:
        _fetch_and_print_services(docker_client, "[BEFORE TEST]")

    yield {
        "stacks": stacks_deployed,
        "services": [service.name for service in docker_client.services.list()],  # type: ignore
    }

    # TEAR DOWN ----------------------

    _fetch_and_print_services(docker_client, "[AFTER TEST]")

    if keep_docker_up:
        # skip bringing the stack down
        return

    # clean up. Guarantees that all services are down before creating a new stack!
    #
    # WORKAROUND https://github.com/moby/moby/issues/30942#issue-207070098
    #
    # docker stack rm services
    # until [ -z "$(docker service ls --filter label=com.docker.stack.namespace=services -q)" ] || [ "$limit" -lt 0 ];do
    # sleep 1;
    # done
    # until [ -z "$(docker network ls --filter label=com.docker.stack.namespace=services -q)" ] || [ "$limit" -lt 0 ];do
    # sleep 1;
    # done

    # make down
    # NOTE: remove them in reverse order since stacks share common networks

    stacks.reverse()
    for _, stack, _ in stacks:
        try:
            subprocess.run(  # noqa: ASYNC221, S603
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
                            # WARNING: rm volumes on this stack might be a problem when shared between different stacks
                            # NOTE: volumes are removed to avoid mixing configs (e.g. postgres db credentials)
                            for resource in pending:
                                resource.remove(force=True)

                        msg = f"Waiting for {len(pending)} {resource_name} to shutdown: {pending}."
                        raise _ResourceStillNotRemovedError(msg)

    _fetch_and_print_services(docker_client, "[AFTER REMOVED]")


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
