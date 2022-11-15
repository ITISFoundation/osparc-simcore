# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import asyncio
from typing import Any, AsyncIterator, Awaitable, Callable, Final, Mapping

import aiodocker
import pytest
from faker import Faker
from fastapi import status
from pydantic import PositiveInt
from simcore_service_autoscaling.utils_docker import (
    eval_cluster_resources,
    pending_services_with_insufficient_resources,
)
from tenacity._asyncio import AsyncRetrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed


async def test_eval_cluster_resource_without_swarm():
    with pytest.raises(aiodocker.DockerError) as exc_info:
        await pending_services_with_insufficient_resources()

    assert exc_info.value.status == status.HTTP_503_SERVICE_UNAVAILABLE

    with pytest.raises(aiodocker.DockerError) as exc_info:
        await eval_cluster_resources()

    assert exc_info.value.status == status.HTTP_503_SERVICE_UNAVAILABLE


@pytest.fixture
async def async_docker_client() -> AsyncIterator[aiodocker.Docker]:
    async with aiodocker.Docker() as docker_client:
        yield docker_client


@pytest.fixture
def task_template() -> dict[str, Any]:
    return {
        "ContainerSpec": {
            "Image": "redis",
        },
    }


_GIGA_NANO_CPU = 10**9


NUM_CPUS = PositiveInt


@pytest.fixture
def create_task_resources() -> Callable[[NUM_CPUS], dict[str, Any]]:
    def _creator(num_cpus: NUM_CPUS) -> dict[str, Any]:
        return {"Resources": {"Reservations": {"NanoCPUs": num_cpus * _GIGA_NANO_CPU}}}

    return _creator


@pytest.fixture
async def create_service(
    async_docker_client: aiodocker.Docker, faker: Faker
) -> AsyncIterator[Callable[[dict[str, Any]], Awaitable[Mapping[str, Any]]]]:
    created_services = []

    async def _creator(task_template: dict[str, Any]) -> Mapping[str, Any]:
        service = await async_docker_client.services.create(
            task_template=task_template, name=f"pytest_{faker.pystr()}"
        )
        assert service
        print(f"--> created docker service f{service}")
        created_services.append(service)
        return service

    yield _creator
    await asyncio.gather(
        *(async_docker_client.services.delete(s["ID"]) for s in created_services)
    )


async def test_pending_services_with_insufficient_resources_with_no_service(
    docker_swarm: None,
):
    assert await pending_services_with_insufficient_resources() == False


async def _assert_for_service_state(
    async_docker_client: aiodocker.Docker,
    created_service: Mapping[str, Any],
    expected_states: list[str],
) -> None:
    SUCCESS_STABLE_TIME_S: Final[float] = 3
    WAIT_TIME: Final[float] = 0.5
    number_of_success = 0
    async for attempt in AsyncRetrying(
        retry=retry_if_exception_type(AssertionError),
        reraise=True,
        wait=wait_fixed(WAIT_TIME),
        stop=stop_after_delay(10 * SUCCESS_STABLE_TIME_S),
    ):
        with attempt:
            print(
                f"--> waiting for service {created_service['ID']} to become {expected_states}..."
            )
            services = await async_docker_client.services.list(
                filters={"id": created_service["ID"]}
            )
            assert services, f"no service with {created_service['ID']}!"
            assert len(services) == 1
            found_service = services[0]

            tasks = await async_docker_client.tasks.list(
                filters={"service": found_service["Spec"]["Name"]}
            )
            assert tasks, f"no tasks available for {found_service['Spec']['Name']}"
            assert len(tasks) == 1
            service_task = tasks[0]
            assert (
                service_task["Status"]["State"] in expected_states
            ), f"service {found_service['Spec']['Name']}'s task is {service_task['Status']['State']}"
            print(
                f"<-- service {found_service['Spec']['Name']} is now {service_task['Status']['State']} {'.'*number_of_success}"
            )
            number_of_success += 1
            assert (number_of_success * WAIT_TIME) >= SUCCESS_STABLE_TIME_S
            print(
                f"<-- service {found_service['Spec']['Name']} is now {service_task['Status']['State']} after {SUCCESS_STABLE_TIME_S} seconds"
            )


async def test_pending_services_with_insufficient_resources_with_service_lacking_resource(
    docker_swarm: None,
    async_docker_client: aiodocker.Docker,
    create_service: Callable[[dict[str, Any]], Awaitable[Mapping[str, Any]]],
    task_template: dict[str, Any],
    create_task_resources: Callable[[NUM_CPUS], dict[str, Any]],
):
    service_with_no_resources = await create_service(task_template)
    await _assert_for_service_state(
        async_docker_client, service_with_no_resources, expected_states=["running"]
    )
    assert await pending_services_with_insufficient_resources() == False
    task_template_with_too_many_resource = task_template | create_task_resources(1000)
    service_with_too_many_resources = await create_service(
        task_template_with_too_many_resource
    )
    await _assert_for_service_state(
        async_docker_client,
        service_with_too_many_resources,
        expected_states=["pending"],
    )
    assert await pending_services_with_insufficient_resources() == True
