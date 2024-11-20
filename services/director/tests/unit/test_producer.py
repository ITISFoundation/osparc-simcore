# pylint:disable=protected-access
# pylint:disable=redefined-outer-name
# pylint:disable=too-many-arguments
# pylint:disable=unused-argument
# pylint:disable=unused-variable

import json
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from typing import Any

import docker
import pytest
from fastapi import FastAPI
from models_library.projects import ProjectID
from models_library.users import UserID
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from settings_library.docker_registry import RegistrySettings
from simcore_service_director import producer
from simcore_service_director.constants import (
    CPU_RESOURCE_LIMIT_KEY,
    MEM_RESOURCE_LIMIT_KEY,
)
from simcore_service_director.core.errors import (
    DirectorRuntimeError,
    ServiceNotAvailableError,
    ServiceUUIDNotFoundError,
)
from simcore_service_director.core.settings import ApplicationSettings
from tenacity import Retrying
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed


@pytest.fixture
def ensure_service_runs_in_ci(
    app_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch
) -> EnvVarsDict:
    return app_environment | setenvs_from_dict(
        monkeypatch,
        envs={
            "DIRECTOR_DEFAULT_MAX_MEMORY": f"{int(25 * pow(1024, 2))}",
            "DIRECTOR_DEFAULT_MAX_NANO_CPUS": f"{int(0.01 * pow(10, 9))}",
        },
    )


@pytest.fixture
async def run_services(
    ensure_service_runs_in_ci: EnvVarsDict,
    configure_registry_access: EnvVarsDict,
    app: FastAPI,
    app_settings: ApplicationSettings,
    push_services,
    docker_swarm: None,
    user_id: UserID,
    project_id: ProjectID,
    docker_client: docker.client.DockerClient,
) -> AsyncIterator[Callable[[int, int], Awaitable[list[dict[str, Any]]]]]:
    started_services = []

    async def push_start_services(
        number_comp: int, number_dyn: int, dependant=False
    ) -> list[dict[str, Any]]:
        pushed_services = await push_services(
            number_of_computational_services=number_comp,
            number_of_interactive_services=number_dyn,
            inter_dependent_services=dependant,
        )
        assert len(pushed_services) == (number_comp + number_dyn)
        for pushed_service in pushed_services:
            service_description = pushed_service["service_description"]
            service_key = service_description["key"]
            service_version = service_description["version"]
            service_port = pushed_service["internal_port"]
            service_entry_point = pushed_service["entry_point"]
            service_uuid = str(uuid.uuid1())
            service_basepath = "/my/base/path"
            with pytest.raises(ServiceUUIDNotFoundError):
                await producer.get_service_details(app, service_uuid)
            # start the service
            started_service = await producer.start_service(
                app,
                f"{user_id}",
                f"{project_id}",
                service_key,
                service_version,
                service_uuid,
                service_basepath,
                "",
            )
            assert "published_port" in started_service
            if service_description["type"] == "dynamic":
                assert not started_service["published_port"]
            assert "entry_point" in started_service
            assert started_service["entry_point"] == service_entry_point
            assert "service_uuid" in started_service
            assert started_service["service_uuid"] == service_uuid
            assert "service_key" in started_service
            assert started_service["service_key"] == service_key
            assert "service_version" in started_service
            assert started_service["service_version"] == service_version
            assert "service_port" in started_service
            assert started_service["service_port"] == service_port
            assert "service_host" in started_service
            assert service_uuid in started_service["service_host"]
            assert "service_basepath" in started_service
            assert started_service["service_basepath"] == service_basepath
            assert "service_state" in started_service
            assert "service_message" in started_service

            # wait for service to be running
            node_details = await producer.get_service_details(app, service_uuid)
            max_time = 60
            for attempt in Retrying(
                wait=wait_fixed(1), stop=stop_after_delay(max_time), reraise=True
            ):
                with attempt:
                    print(
                        f"--> waiting for {started_service['service_key']}:{started_service['service_version']} to run..."
                    )
                    node_details = await producer.get_service_details(app, service_uuid)
                    print(
                        f"<-- {started_service['service_key']}:{started_service['service_version']} state is {node_details['service_state']} using {app_settings.DIRECTOR_DEFAULT_MAX_MEMORY}Bytes, {app_settings.DIRECTOR_DEFAULT_MAX_NANO_CPUS}nanocpus"
                    )
                    for service in docker_client.services.list():
                        tasks = service.tasks()
                        print(
                            f"service details {service.id}:{service.name}: {json.dumps( tasks, indent=2)}"
                        )
                    assert (
                        node_details["service_state"] == "running"
                    ), f"current state is {node_details['service_state']}"

            started_service["service_state"] = node_details["service_state"]
            started_service["service_message"] = node_details["service_message"]
            assert node_details == started_service
            started_services.append(started_service)
        return started_services

    yield push_start_services
    # teardown stop the services
    for service in started_services:
        service_uuid = service["service_uuid"]
        # NOTE: Fake services are not even web-services therefore we cannot
        # even emulate a legacy dy-service that does not implement a save-state feature
        # so here we must make save_state=False
        await producer.stop_service(app, node_uuid=service_uuid, save_state=False)
        with pytest.raises(ServiceUUIDNotFoundError):
            await producer.get_service_details(app, service_uuid)


async def test_find_service_tag():
    my_service_key = "myservice-key"
    list_of_images = {
        my_service_key: [
            "2.4.0",
            "2.11.0",
            "2.8.0",
            "1.2.1",
            "some wrong value",
            "latest",
            "1.2.0",
            "1.2.3",
        ]
    }
    with pytest.raises(ServiceNotAvailableError):
        await producer._find_service_tag(  # noqa: SLF001
            list_of_images, "some_wrong_key", None
        )
    with pytest.raises(ServiceNotAvailableError):
        await producer._find_service_tag(  # noqa: SLF001
            list_of_images, my_service_key, "some wrong key"
        )
    # get the latest (e.g. 2.11.0)
    latest_version = await producer._find_service_tag(  # noqa: SLF001
        list_of_images, my_service_key, None
    )
    assert latest_version == "2.11.0"
    latest_version = await producer._find_service_tag(  # noqa: SLF001
        list_of_images, my_service_key, "latest"
    )
    assert latest_version == "2.11.0"
    # get a specific version
    await producer._find_service_tag(  # noqa: SLF001
        list_of_images, my_service_key, "1.2.3"
    )


async def test_start_stop_service(
    configure_registry_access: EnvVarsDict,
    configured_docker_network: EnvVarsDict,
    run_services: Callable[..., Awaitable[list[dict[str, Any]]]],
):
    # standard test
    await run_services(number_comp=1, number_dyn=1)


async def test_service_assigned_env_variables(
    configure_registry_access: EnvVarsDict,
    configured_docker_network: EnvVarsDict,
    run_services: Callable[..., Awaitable[list[dict[str, Any]]]],
    user_id: UserID,
    project_id: ProjectID,
):
    started_services = await run_services(number_comp=1, number_dyn=1)
    client = docker.from_env()
    for service in started_services:
        service_uuid = service["service_uuid"]
        list_of_services = client.services.list(
            filters={"label": f"io.simcore.runtime.node-id={service_uuid}"}
        )
        assert len(list_of_services) == 1
        docker_service = list_of_services[0]
        # check env
        docker_tasks = docker_service.tasks()
        assert len(docker_tasks) > 0
        task = docker_tasks[0]
        envs_list = task["Spec"]["ContainerSpec"]["Env"]
        envs_dict = dict(x.split("=") for x in envs_list)

        assert "POSTGRES_ENDPOINT" in envs_dict
        assert "POSTGRES_USER" in envs_dict
        assert "POSTGRES_PASSWORD" in envs_dict
        assert "POSTGRES_DB" in envs_dict
        assert "STORAGE_ENDPOINT" in envs_dict

        assert "SIMCORE_USER_ID" in envs_dict
        assert envs_dict["SIMCORE_USER_ID"] == f"{user_id}"
        assert "SIMCORE_NODE_UUID" in envs_dict
        assert envs_dict["SIMCORE_NODE_UUID"] == service_uuid
        assert "SIMCORE_PROJECT_ID" in envs_dict
        assert envs_dict["SIMCORE_PROJECT_ID"] == f"{project_id}"
        assert "SIMCORE_NODE_BASEPATH" in envs_dict
        assert envs_dict["SIMCORE_NODE_BASEPATH"] == service["service_basepath"]
        assert "SIMCORE_HOST_NAME" in envs_dict
        assert envs_dict["SIMCORE_HOST_NAME"] == docker_service.name

        assert MEM_RESOURCE_LIMIT_KEY in envs_dict
        assert CPU_RESOURCE_LIMIT_KEY in envs_dict


async def test_interactive_service_published_port(
    configure_registry_access: EnvVarsDict,
    configured_docker_network: EnvVarsDict,
    run_services,
):
    running_dynamic_services = await run_services(number_comp=0, number_dyn=1)
    assert len(running_dynamic_services) == 1

    service = running_dynamic_services[0]
    assert "published_port" in service

    service_port = service["published_port"]
    # ports are not published anymore in production mode
    assert not service_port

    client = docker.from_env()
    service_uuid = service["service_uuid"]
    list_of_services = client.services.list(
        filters={"label": f"io.simcore.runtime.node-id={service_uuid}"}
    )
    assert len(list_of_services) == 1

    docker_service = list_of_services[0]
    # no port open to the outside
    assert not docker_service.attrs["Endpoint"]["Spec"]
    # service is started with dnsrr (round-robin) mode
    assert docker_service.attrs["Spec"]["EndpointSpec"]["Mode"] == "dnsrr"


async def test_interactive_service_in_correct_network(
    configure_registry_access: EnvVarsDict,
    with_docker_network: dict[str, Any],
    configured_docker_network: EnvVarsDict,
    run_services,
):
    running_dynamic_services = await run_services(
        number_comp=0, number_dyn=2, dependant=False
    )
    assert len(running_dynamic_services) == 2
    for service in running_dynamic_services:
        client = docker.from_env()
        service_uuid = service["service_uuid"]
        list_of_services = client.services.list(
            filters={"label": f"io.simcore.runtime.node-id={service_uuid}"}
        )
        assert list_of_services
        assert len(list_of_services) == 1
        docker_service = list_of_services[0]
        assert (
            docker_service.attrs["Spec"]["Networks"][0]["Target"]
            == with_docker_network["Id"]
        )


async def test_dependent_services_have_common_network(
    configure_registry_access: EnvVarsDict,
    configured_docker_network: EnvVarsDict,
    run_services,
):
    running_dynamic_services = await run_services(
        number_comp=0, number_dyn=2, dependant=True
    )
    assert len(running_dynamic_services) == 2

    for service in running_dynamic_services:
        client = docker.from_env()
        service_uuid = service["service_uuid"]
        list_of_services = client.services.list(
            filters={"label": f"io.simcore.runtime.node-id={service_uuid}"}
        )
        # there is one dependency per service
        assert len(list_of_services) == 2
        # check they have same network
        assert (
            list_of_services[0].attrs["Spec"]["Networks"][0]["Target"]
            == list_of_services[1].attrs["Spec"]["Networks"][0]["Target"]
        )


@dataclass
class FakeDockerService:
    service_str: str
    expected_key: str
    expected_tag: str


@pytest.fixture
def registry_settings(app_settings: ApplicationSettings) -> RegistrySettings:
    return app_settings.DIRECTOR_REGISTRY


@pytest.mark.parametrize(
    "fake_service",
    [
        FakeDockerService(
            "/simcore/services/dynamic/some/sub/folder/my_service-key:123.456.3214",
            "simcore/services/dynamic/some/sub/folder/my_service-key",
            "123.456.3214",
        ),
        FakeDockerService(
            "/simcore/services/dynamic/some/sub/folder/my_service-key:123.456.3214@sha256:2aef165ab4f30fbb109e88959271d8b57489790ea13a77d27c02d8adb8feb20f",
            "simcore/services/dynamic/some/sub/folder/my_service-key",
            "123.456.3214",
        ),
    ],
)
async def test_get_service_key_version_from_docker_service(
    configure_registry_access: EnvVarsDict,
    registry_settings: RegistrySettings,
    fake_service: FakeDockerService,
):
    docker_service_partial_inspect = {
        "Spec": {
            "TaskTemplate": {
                "ContainerSpec": {
                    "Image": f"{registry_settings.resolved_registry_url}{fake_service.service_str}"
                }
            }
        }
    }
    (
        service_key,
        service_tag,
    ) = await producer._get_service_key_version_from_docker_service(  # noqa: SLF001
        docker_service_partial_inspect, registry_settings
    )
    assert service_key == fake_service.expected_key
    assert service_tag == fake_service.expected_tag


@pytest.mark.parametrize(
    "fake_service_str",
    [
        "postgres:14.8-alpine@sha256:150dd39ccb7ae6c7ba6130c3582c39a30bb5d3d22cb08ad0ba37001e3f829abc",
        "/simcore/postgres:14.8-alpine@sha256:150dd39ccb7ae6c7ba6130c3582c39a30bb5d3d22cb08ad0ba37001e3f829abc",
        "itisfoundation/postgres:14.8-alpine@sha256:150dd39ccb7ae6c7ba6130c3582c39a30bb5d3d22cb08ad0ba37001e3f829abc",
        "/simcore/services/stuff/postgres:10.11",
    ],
)
async def test_get_service_key_version_from_docker_service_except_invalid_keys(
    configure_registry_access: EnvVarsDict,
    registry_settings: RegistrySettings,
    fake_service_str: str,
):
    docker_service_partial_inspect = {
        "Spec": {
            "TaskTemplate": {
                "ContainerSpec": {
                    "Image": f"{registry_settings.resolved_registry_url if fake_service_str.startswith('/') else ''}{fake_service_str}"
                }
            }
        }
    }
    with pytest.raises(DirectorRuntimeError):
        await producer._get_service_key_version_from_docker_service(  # noqa: SLF001
            docker_service_partial_inspect, registry_settings
        )
