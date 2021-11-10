# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import asyncio
import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import Any, List, Mapping, Tuple

import aiodocker
import docker
import pytest
import yaml
from pytest_simcore.helpers.constants import MINUTE
from pytest_simcore.helpers.typing_docker import ServiceDict, TaskDict, UrlStr
from pytest_simcore.helpers.typing_tenacity import TenacityStatsDict
from pytest_simcore.helpers.utils_dict import copy_from_dict, get_from_dict
from pytest_simcore.helpers.utils_environs import EnvVarsDict
from tenacity._asyncio import AsyncRetrying
from tenacity.before_sleep import before_sleep_log
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_random

## HELPERS ----------------------------------------------------------------------

log = logging.getLogger(__name__)


async def assert_service_is_running(
    service_id: str, docker, *, max_running_delay=1 * MINUTE
) -> Tuple[List[TaskDict], TenacityStatsDict]:

    assert max_running_delay > 0.5 * MINUTE

    #
    # The retry-policy constraints in this test
    # the time a service takes since it is deployed by the swarm
    # until it is running (i.e. started and healthy)
    #
    retry_policy = dict(
        # instead of wait_fix in order to help parallel execution in asyncio.gather
        wait=wait_random(1, 2),
        # notice that the precision of stop is determined by wait
        stop=stop_after_delay(max_running_delay + 2),
        before_sleep=before_sleep_log(log, logging.INFO),
        reraise=True,
    )

    async for attempt in AsyncRetrying(**retry_policy):
        with attempt:
            service: ServiceDict = await docker.services.inspect(service_id)

            assert service_id == service["ID"]

            service_name = service["Spec"]["Name"]
            num_replicas = int(
                get_from_dict(service, "Spec.Mode.Replicated.Replicas", default=1)
            )

            tasks: List[TaskDict] = await docker.tasks.list(
                filters={"service": service_name}
            )

            tasks_current_state = [task["Status"]["State"] for task in tasks]
            num_running = sum(current == "running" for current in tasks_current_state)

            is_running: bool = num_replicas == num_running

            logs: str = ""
            if not is_running:
                logs_list = await docker.services.logs(
                    service_id,
                    follow=False,
                    stdout=True,
                    stderr=True,
                )
                for line in logs_list:
                    logs += line

            tasks_info = [
                json.dumps(
                    copy_from_dict(
                        task,
                        include={
                            "ID": ...,
                            "CreatedAt": ...,
                            "UpdatedAt": ...,
                            "Spec": {"ContainerSpec": {"Image"}},
                            "Status": {"Timestamp", "State", "ContainerStatus"},
                            "DesiredState": ...,
                        },
                    ),
                    indent=1,
                )
                for task in tasks
            ]

            assert is_running, (
                f"{service_name=} has {tasks_current_state=}, but expected at least {num_replicas=} running. "
                f"Details:\n"
                f"{tasks_info=}\n"
                f"{logs=}\n"
            )

            return tasks, attempt.retry_state.retry_object.statistics
    assert False  # never reached


## FIXTURES ----------------------------------------------------------------------


@pytest.fixture
async def docker_async_client():
    client = aiodocker.Docker()
    try:
        yield client
    finally:
        await client.close()


@pytest.fixture(scope="module")
def core_stack_namespace(testing_environ_vars: EnvVarsDict) -> str:
    """returns 'com.docker.stack.namespace' service label expected core stack"""
    stack_name = testing_environ_vars["SWARM_STACK_NAME"]
    assert stack_name is not None
    return stack_name


@pytest.fixture(scope="module")
def core_stack_services_names(
    core_docker_compose_file: Path, core_stack_namespace: str
) -> List[str]:
    """Expected names of service in core stack at runtime"""
    spec_service_names = yaml.safe_load(core_docker_compose_file.read_text())[
        "services"
    ].keys()
    return sorted(f"{core_stack_namespace}_{s}" for s in spec_service_names)


@pytest.fixture(scope="module")
def docker_stack_core_and_ops(
    # docker_registry: UrlStr,
    docker_swarm: None,
    docker_client: docker.client.DockerClient,
    core_docker_compose_file: Path,
    ops_docker_compose_file: Path,
    core_stack_namespace: str,
):

    for key, stack_name, compose_file in [
        (
            "core",
            core_stack_namespace,
            core_docker_compose_file,
        ),
        (
            "ops",
            "pytest-ops",
            ops_docker_compose_file,
        ),
    ]:
        print(f"deploying {key}", "-" * 10)
        subprocess.run(
            f"docker stack deploy --with-registry-auth -c {compose_file.name} {stack_name}",
            shell=True,
            check=True,
            cwd=compose_file.parent,
        )
        subprocess.run(f"docker stack ps {stack_name}", shell=True, check=False)


## TESTS ----------------------------------------------------------------------


async def test_core_services_running(
    loop,
    docker_stack_core_and_ops: None,
    core_stack_namespace: str,
    docker_async_client: aiodocker.Docker,
    core_stack_services_names: List[str],
):
    docker = docker_async_client

    core_services: List[ServiceDict] = await docker.services.list(
        filters={"label": f"com.docker.stack.namespace={core_stack_namespace}"}
    )
    assert core_services
    assert sorted(s["Spec"]["Name"] for s in core_services) == core_stack_services_names

    results = await asyncio.gather(
        *(
            assert_service_is_running(
                service["ID"], docker, max_running_delay=1 * MINUTE
            )
            for service in core_services
        ),
        return_exceptions=False,
    )

    try:
        assert not any(isinstance(r, Exception) for r in results)

    finally:
        print("test_core_services_running stats", "-" * 10)
        for res, service in zip(results, core_services):
            print(f"{service['Spec']['Name']:-^50}")
            print(
                res if isinstance(res, Exception) else json.dumps(res),
            )


if __name__ == "__main__":
    # NOTE: use in vscode "Run and Debug" -> select 'Python: Current File'
    sys.exit(
        pytest.main(["-vv", "-s", "--pdb", "--log-cli-level=WARNING", sys.argv[0]])
    )
