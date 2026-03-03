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

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Phased deployment batches (mirrors Makefile APP_BATCH_1..6 + INFRA_SERVICES)
# ---------------------------------------------------------------------------

INFRA_SERVICES: list[str] = ["postgres", "redis", "rabbit", "migration"]

APP_BATCHES: list[list[str]] = [
    ["catalog", "director", "agent", "docker-api-proxy", "static-webserver"],
    ["storage", "sto-worker", "sto-worker-cpu-bound", "dask-scheduler", "dask-sidecar"],
    ["director-v2", "dynamic-schdlr", "wb-garbage-collector", "wb-api-server", "wb-auth"],
    ["wb-db-event-listener", "webserver", "autoscaling", "clusters-keeper", "resource-usage-tracker"],
    ["efs-guardian", "api-server", "api-worker", "datcore-adapter", "invitations"],
    ["notifications", "notifications-worker", "payments", "traefik", "traefik-config-placeholder"],
]


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
    before_sleep=before_sleep_log(log, logging.INFO),
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

    log.info(
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


def _write_filtered_compose(
    full_compose: dict,
    services_to_include: list[str],
    output_path: Path,
) -> Path:
    """Write a compose file that only contains *services_to_include*."""
    filtered = deepcopy(full_compose)
    all_services = set(filtered.get("services", {}))
    for name in all_services - set(services_to_include):
        filtered["services"].pop(name, None)
    with output_path.open("w") as fh:
        yaml.dump(filtered, fh, default_flow_style=False)
    return output_path


async def _async_assert_service_is_running(
    async_docker: aiodocker.Docker,
    service_name: str,
    stack_name: str,
) -> None:
    """Check that a swarm service has the expected number of running tasks.

    Uses *aiodocker* so that many services can be polled concurrently with
    ``asyncio.gather``.
    """
    full_service_name = f"{stack_name}_{service_name}"

    async for attempt in AsyncRetrying(
        wait=wait_fixed(0.1),
        stop=stop_after_delay(8 * MINUTE),
        before_sleep=before_sleep_log(log, logging.INFO),
        reraise=True,
    ):
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
            log.info("--> %s is up and running!", full_service_name)


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
        log.info(
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
    log.info(
        "Waiting for %d service(s) to become ready: %s",
        len(service_names),
        service_names,
    )
    await asyncio.gather(*(_async_assert_service_is_running(async_docker, name, stack_name) for name in service_names))


def _compute_deployment_batches(
    selected_services: set[str],
) -> list[list[str]]:
    """Return ordered batches of services to deploy, filtered to *selected_services*.

    Infrastructure services come first, then APP_BATCHES in order. Any
    selected service not present in the predefined batches is appended as a
    final batch so nothing is missed.
    """
    batches: list[list[str]] = []
    accounted_for: set[str] = set()

    # Phase 1 - infrastructure
    infra = [s for s in INFRA_SERVICES if s in selected_services]
    if infra:
        batches.append(infra)
        accounted_for.update(infra)

    # Phase 2 - application batches
    for batch_template in APP_BATCHES:
        batch = [s for s in batch_template if s in selected_services]
        if batch:
            batches.append(batch)
            accounted_for.update(batch)

    # Catch-all - services in the selection but not in any predefined batch
    remaining = sorted(selected_services - accounted_for)
    if remaining:
        batches.append(remaining)

    return batches


async def _deploy_core_stack_phased(
    compose_file: Path,
    stack_name: str,
    full_compose: dict,
    selected_services: set[str],
) -> None:
    """Deploy the core stack in batches, waiting for each batch to be ready.

    Mirrors the Makefile ``up-prod-phased`` target.  Each batch is deployed
    by writing a filtered compose file and calling ``docker stack deploy``
    with the accumulated set of services so far.
    """
    batches = _compute_deployment_batches(selected_services)
    cumulative_services: list[str] = []

    async with aiodocker.Docker() as async_docker:
        for batch_idx, batch in enumerate(batches, start=1):
            # Skip services that are already running
            services_to_start = await _filter_already_running(async_docker, batch, stack_name)

            cumulative_services.extend(batch)
            is_last_batch = batch_idx == len(batches)

            if not services_to_start:
                log.info(
                    "Phase %d/%d: all services already running, skipping deploy",
                    batch_idx,
                    len(batches),
                )
                continue

            if is_last_batch:
                # Final batch - deploy the original (complete) compose file
                deploy_file = compose_file
            else:
                deploy_file = _write_filtered_compose(
                    full_compose,
                    cumulative_services,
                    compose_file.parent / f".phased-batch-{batch_idx}.yml",
                )

            log.info(
                "Phase %d/%d: deploying %s (cumulative: %d services)",
                batch_idx,
                len(batches),
                services_to_start,
                len(cumulative_services),
            )
            _deploy_stack(deploy_file, stack_name)
            await _wait_for_services_running(async_docker, services_to_start, stack_name)


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

    # Deploy core stack in phases (infra → app batches) using aiodocker
    core_compose = yaml.safe_load(core_docker_compose_file.read_text())
    selected_services = set(core_compose.get("services", {}))

    try:
        await _deploy_core_stack_phased(
            compose_file=core_docker_compose_file,
            stack_name=core_stack_name,
            full_compose=core_compose,
            selected_services=selected_services,
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
            log.warning(
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
                before_sleep=before_sleep_log(log, logging.INFO),
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
