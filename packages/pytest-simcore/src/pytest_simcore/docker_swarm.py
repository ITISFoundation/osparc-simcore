# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


import json
import logging
import subprocess
from pathlib import Path
from typing import Dict, Iterator

import docker
import pytest
import tenacity
import yaml
from docker.errors import APIError
from tenacity import Retrying
from tenacity.before_sleep import before_sleep_log
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_random

from .helpers.utils_docker import get_ip
from .helpers.utils_environs import EnvVarsDict

log = logging.getLogger(__name__)


#
# NOTE this file must be PYTHON >=3.6 COMPATIBLE because it is used by the director service
#

# HELPERS --------------------------------------------------------------------------------

_MINUTE: int = 60  # secs
_HEADER: str = "{:-^50}"


class _NotInSwarmException(Exception):
    pass


class _ResourceStillNotRemoved(Exception):
    pass


def _in_docker_swarm(
    docker_client: docker.client.DockerClient, raise_error: bool = False
) -> bool:
    try:
        docker_client.swarm.reload()
        inspect_result = docker_client.swarm.attrs
        assert type(inspect_result) == dict
    except APIError as error:
        if raise_error:
            raise _NotInSwarmException() from error
        return False
    return True


@tenacity.retry(
    wait=wait_random(min=5, max=10),
    stop=stop_after_delay(4 * _MINUTE),
    before_sleep=before_sleep_log(log, logging.INFO),
    reraise=True,
)
def assert_deployed_services_are_ready(
    docker_client: docker.client.DockerClient,
) -> None:
    def _get(obj, name, default=None):
        parts = name.split(".")
        value = obj
        for part in parts[:-1]:
            value = value.get(part, {})
        return value.get(parts[-1], default)

    for service in docker_client.services.list():
        service_name = service.name
        num_replicas_specified = _get(
            service.attrs, "Spec.Mode.Replicated.Replicas", default=1
        )

        print(
            f"Waiting for service_name='{service_name}' to have num_replicas_specified={num_replicas_specified} ..."
        )
        tasks = list(service.tasks())

        if tasks:
            #
            # WARNING:
            #  we have noticed using the 'last updated' task is not necessarily
            #  the most actual of the tasks. It dependends e.g. on the restart policy.
            #  For that reason, the readiness condition has been redefined as state in which
            #  the specified number of replicas reach their desired state.
            #  We still wonder if there is a transition point in which that condition
            #  is met while still the service is not ready. This needs to be reviewed...
            #

            tasks_desired_state = [task["DesiredState"] for task in tasks]
            tasks_current_state = [task["Status"]["State"] for task in tasks]

            num_ready = sum(
                [
                    desired == current
                    for desired, current in zip(
                        tasks_desired_state, tasks_current_state
                    )
                ]
            )

            assert num_ready == num_replicas_specified, (
                f"service_name='{service_name}' not ready: tasks_current_state={tasks_current_state} "
                f"but tasks_desired_state={tasks_desired_state}."
            )


def _print_services(docker_client: docker.client.DockerClient, msg: str) -> None:
    print("{:*^100}".format("docker services running " + msg))
    services = {
        s.name: {"service": s.attrs, "tasks": list(s.tasks())}
        for s in docker_client.services.list()
    }
    print(json.dumps(services, indent=1, sort_keys=True))
    print("-" * 100)


# FIXTURES --------------------------------------------------------------------------------


@pytest.fixture(scope="session")
def docker_client() -> Iterator[docker.client.DockerClient]:
    client = docker.from_env()
    yield client


@pytest.fixture(scope="session")
def keep_docker_up(request) -> bool:
    return request.config.getoption("--keep-docker-up")


@pytest.fixture(scope="module")
def docker_swarm(
    docker_client: docker.client.DockerClient, keep_docker_up: Iterator[bool]
) -> Iterator[None]:
    for attempt in Retrying(
        wait=wait_random(5), stop=stop_after_delay(15), reraise=True
    ):
        with attempt:
            if not _in_docker_swarm(docker_client):
                docker_client.swarm.init(advertise_addr=get_ip())
            # if still not in swarm, raise an error to try and initialize again
            _in_docker_swarm(docker_client, raise_error=True)

    assert _in_docker_swarm(docker_client) is True

    yield

    if not keep_docker_up:
        assert docker_client.swarm.leave(force=True)

    assert _in_docker_swarm(docker_client) is keep_docker_up


@pytest.fixture(scope="module")
def docker_stack(
    docker_swarm,
    docker_client: docker.client.DockerClient,
    core_docker_compose_file: Path,
    ops_docker_compose_file: Path,
    keep_docker_up: bool,
    testing_environ_vars: EnvVarsDict,
) -> Iterator[Dict]:

    # WARNING: keep prefix "pytest-" in stack names
    core_stack_name = testing_environ_vars["SWARM_STACK_NAME"]
    ops_stack_name = "pytest-ops"

    assert core_stack_name
    assert core_stack_name.startswith("pytest-")
    stacks = [
        (
            "core",
            core_stack_name,
            core_docker_compose_file,
        ),
        (
            "ops",
            ops_stack_name,
            ops_docker_compose_file,
        ),
    ]

    # make up-version
    stacks_deployed: Dict[str, Dict] = {}
    for key, stack_name, compose_file in stacks:
        subprocess.run(
            f"docker stack deploy --with-registry-auth -c {compose_file.name} {stack_name}",
            shell=True,
            check=True,
            cwd=compose_file.parent,
        )
        stacks_deployed[key] = {
            "name": stack_name,
            "compose": yaml.safe_load(compose_file.read_text()),
        }

    assert_deployed_services_are_ready(docker_client)
    _print_services(docker_client, "[BEFORE TEST]")

    yield {
        "stacks": stacks_deployed,
        "services": [service.name for service in docker_client.services.list()],
    }

    ## TEAR DOWN ----------------------

    _print_services(docker_client, "[AFTER TEST]")

    if keep_docker_up:
        # skip bringing the stack down
        return

    # clean up. Guarantees that all services are down before creating a new stack!
    #
    # WORKAROUND https://github.com/moby/moby/issues/30942#issue-207070098
    #
    #   docker stack rm services
    #   until [ -z "$(docker service ls --filter label=com.docker.stack.namespace=services -q)" ] || [ "$limit" -lt 0 ]; do
    #   sleep 1;
    #   done
    #   until [ -z "$(docker network ls --filter label=com.docker.stack.namespace=services -q)" ] || [ "$limit" -lt 0 ]; do
    #   sleep 1;
    #   done

    # make down
    # NOTE: remove them in reverse order since stacks share common networks

    stacks.reverse()
    for _, stack, _ in stacks:

        try:
            subprocess.run(
                f"docker stack remove {stack}",
                shell=True,
                check=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError as err:
            log.warning(
                "Ignoring failure while executing '%s' (returned code %d):\n%s\n%s\n%s\n%s\n",
                err.cmd,
                err.returncode,
                _HEADER.format("stdout"),
                err.stdout.decode("utf8") if err.stdout else "",
                _HEADER.format("stderr"),
                err.stderr.decode("utf8") if err.stderr else "",
            )

        # Waits that all resources get removed or force them
        # The check order is intentional because some resources depend on others to be removed
        # e.g. cannot remove networks/volumes used by running containers
        for resource_name in ("services", "containers", "volumes", "networks"):
            resource_client = getattr(docker_client, resource_name)

            for attempt in Retrying(
                wait=wait_random(max=20),
                stop=stop_after_delay(3 * _MINUTE),
                before_sleep=before_sleep_log(log, logging.WARNING),
                reraise=True,
            ):
                with attempt:
                    pending = resource_client.list(
                        filters={"label": f"com.docker.stack.namespace={stack}"}
                    )
                    if pending:
                        if resource_name in ("volumes",):
                            # WARNING: rm volumes on this stack migh be a problem when shared between different stacks
                            # NOTE: volumes are removed to avoid mixing configs (e.g. postgres db credentials)
                            for resource in pending:
                                resource.remove(force=True)

                        raise _ResourceStillNotRemoved(
                            f"Waiting for {len(pending)} {resource_name} to shutdown: {pending}."
                        )

    _print_services(docker_client, "[AFTER REMOVED]")
