# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import json
import logging
import subprocess
import time
from datetime import datetime
from pathlib import Path
from pprint import pprint
from typing import Dict, Iterator, Type

import docker
import pytest
import tenacity
import yaml
from docker.errors import APIError
from tenacity.before_sleep import before_sleep_log
from tenacity.stop import stop_after_attempt, stop_after_delay
from tenacity.wait import wait_exponential, wait_fixed

from .helpers.utils_docker import get_ip
from .helpers.utils_environs import EnvVarsDict

log = logging.getLogger(__name__)


class _NotInSwarmException(Exception):
    pass


class _StillInSwarmException(Exception):
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


def _attempt_for(retry_error_cls: Type[Exception]) -> tenacity.Retrying:
    return tenacity.Retrying(
        wait=wait_exponential(),
        stop=stop_after_delay(15),
        retry_error_cls=retry_error_cls,
    )


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
    for attempt in _attempt_for(retry_error_cls=_NotInSwarmException):
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


def to_datetime(datetime_str: str) -> datetime:
    # datetime_str is typically '2020-10-09T12:28:14.771034099Z'
    #  - The T separates the date portion from the time-of-day portion
    #  - The Z on the end means UTC, that is, an offset-from-UTC
    # The 099 before the Z is not clear, therefore we will truncate the last part
    N = len("2020-10-09T12:28:14.7710")
    if len(datetime_str) > N:
        datetime_str = datetime_str[:N]
    return datetime.strptime(datetime_str, "%Y-%m-%dT%H:%M:%S.%f")


def by_task_update(task: Dict) -> datetime:
    datetime_str = task["Status"]["Timestamp"]
    return to_datetime(datetime_str)


@tenacity.retry(
    wait=wait_fixed(5),
    stop=stop_after_attempt(20),
    before_sleep=before_sleep_log(log, logging.INFO),
    reraise=True,
)
def _wait_for_services(docker_client: docker.client.DockerClient) -> None:
    pre_states = ["NEW", "PENDING", "ASSIGNED", "PREPARING", "STARTING"]
    services = docker_client.services.list()
    for service in services:
        print(f"Waiting for {service.name}...")
        if service.tasks():
            sorted_tasks = sorted(service.tasks(), key=by_task_update)
            task = sorted_tasks[-1]
            task_state = task["Status"]["State"].upper()
            if task_state not in pre_states:
                if not task_state == "RUNNING":
                    raise ValueError(
                        f"service {service.name} not running [task_state={task_state} instead]. "
                        f"Details: \n{json.dumps(task, indent=2)}"
                    )


def _print_services(docker_client: docker.client.DockerClient, msg: str) -> None:
    print("{:*^100}".format("docker services running " + msg))
    for service in docker_client.services.list():
        pprint(service.attrs)
    print("-" * 100)


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

    _wait_for_services(docker_client)
    _print_services(docker_client, "[BEFORE TEST]")

    yield {
        "stacks": stacks_deployed,
        "services": [service.name for service in docker_client.services.list()],
    }

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
    WAIT_BEFORE_RETRY_SECS = 1

    HEADER = "{:-^20}"
    stacks.reverse()
    for _, stack, _ in stacks:

        try:
            subprocess.run(f"docker stack remove {stack}", shell=True, check=True)
        except subprocess.CalledProcessError as err:
            log.warning(
                "Ignoring failure while executing '%s' (returned code %d):\n%s\n%s\n%s\n%s\n",
                err.cmd,
                err.returncode,
                HEADER.format("stdout"),
                err.stdout,
                HEADER.format("stderr"),
                err.stderr,
            )

        while docker_client.services.list(
            filters={"label": f"com.docker.stack.namespace={stack}"}
        ):
            time.sleep(WAIT_BEFORE_RETRY_SECS)

        while docker_client.networks.list(
            filters={"label": f"com.docker.stack.namespace={stack}"}
        ):
            time.sleep(WAIT_BEFORE_RETRY_SECS)

        while docker_client.containers.list(
            filters={"label": f"com.docker.stack.namespace={stack}"}
        ):
            time.sleep(WAIT_BEFORE_RETRY_SECS)

        for attempt in _attempt_for(retry_error_cls=APIError):
            with attempt:
                list_of_volumes = docker_client.volumes.list(
                    filters={"label": f"com.docker.stack.namespace={stack}"}
                )
                for volume in list_of_volumes:
                    volume.remove(force=True)

    _print_services(docker_client, "[AFTER REMOVED]")
