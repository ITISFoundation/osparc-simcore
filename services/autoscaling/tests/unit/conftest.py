# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import asyncio
from pathlib import Path
from typing import Any, AsyncIterator, Awaitable, Callable, Final, Mapping, Optional

import aiodocker
import httpx
import pytest
import simcore_service_autoscaling
from asgi_lifespan import LifespanManager
from deepdiff import DeepDiff
from faker import Faker
from fastapi import FastAPI
from pydantic import PositiveInt
from pytest import MonkeyPatch
from pytest_simcore.helpers.utils_envs import EnvVarsDict, setenvs_from_dict
from simcore_service_autoscaling.core.application import create_app
from simcore_service_autoscaling.core.settings import ApplicationSettings
from tenacity._asyncio import AsyncRetrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

pytest_plugins = [
    "pytest_simcore.docker_swarm",
    "pytest_simcore.environment_configs",
    "pytest_simcore.repository_paths",
]


@pytest.fixture(scope="session")
def project_slug_dir(osparc_simcore_root_dir: Path) -> Path:
    # fixtures in pytest_simcore.environs
    service_folder = osparc_simcore_root_dir / "services" / "autoscaling"
    assert service_folder.exists()
    assert any(service_folder.glob("src/simcore_service_autoscaling"))
    return service_folder


@pytest.fixture(scope="session")
def installed_package_dir() -> Path:
    dirpath = Path(simcore_service_autoscaling.__file__).resolve().parent
    assert dirpath.exists()
    return dirpath


@pytest.fixture
def app_environment(
    mock_env_devel_environment: EnvVarsDict, monkeypatch: MonkeyPatch, faker: Faker
) -> EnvVarsDict:
    # SEE https://faker.readthedocs.io/en/master/providers/faker.providers.internet.html?highlight=internet#faker-providers-internet
    envs = setenvs_from_dict(
        monkeypatch,
        {
            "AWS_KEY_NAME": "TODO",
            "AWS_DNS": faker.domain_name(),
            "AWS_ACCESS_KEY_ID": "str",
            "AWS_SECRET_ACCESS_KEY": "str",
            "AWS_SECURITY_GROUP_IDS": '["a", "b"]',
            "AWS_SUBNET_ID": "str",
        },
    )
    return mock_env_devel_environment | envs


@pytest.fixture(scope="function")
async def initialized_app(app_environment: EnvVarsDict) -> AsyncIterator[FastAPI]:
    settings = ApplicationSettings.create_from_envs()
    app = create_app(settings)
    async with LifespanManager(app):
        yield app


@pytest.fixture
def app_settings(initialized_app: FastAPI) -> ApplicationSettings:
    assert initialized_app.state.settings
    return initialized_app.state.settings


@pytest.fixture(scope="function")
async def async_client(initialized_app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:

    async with httpx.AsyncClient(
        app=initialized_app,
        base_url="http://director-v2.testserver.io",
        headers={"Content-Type": "application/json"},
    ) as client:
        yield client


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
) -> AsyncIterator[
    Callable[[dict[str, Any], Optional[dict[str, str]]], Awaitable[Mapping[str, Any]]]
]:
    created_services = []

    async def _creator(
        task_template: dict[str, Any], labels: Optional[dict[str, str]] = None
    ) -> Mapping[str, Any]:
        service_name = f"pytest_{faker.pystr()}"
        service = await async_docker_client.services.create(
            task_template=task_template,
            name=service_name,
            labels=labels or {},  # type: ignore
        )
        assert service
        print(f"--> created docker service f{service}")
        created_services.append(service)
        # get more info on that service
        service = await async_docker_client.services.inspect(service["ID"])
        assert service["Spec"]["Name"] == service_name
        diff = DeepDiff(
            task_template,
            service["Spec"]["TaskTemplate"],
            exclude_paths={
                "ForceUpdate",
                "Runtime",
                "root['ContainerSpec']['Isolation']",
            },
        )
        assert not diff, f"{diff}"
        assert service["Spec"]["Labels"] == (labels or {})

        return service

    yield _creator
    await asyncio.gather(
        *(async_docker_client.services.delete(s["ID"]) for s in created_services)
    )


@pytest.fixture
def assert_for_service_state() -> Callable[
    [aiodocker.Docker, Mapping[str, Any], list[str]], Awaitable[None]
]:
    async def _runner(
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

    return _runner
