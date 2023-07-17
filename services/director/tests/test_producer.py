# pylint:disable=protected-access
# pylint:disable=redefined-outer-name
# pylint:disable=too-many-arguments
# pylint:disable=unused-argument
# pylint:disable=unused-variable

import json
import uuid
from dataclasses import dataclass
from typing import Callable

import docker
import pytest
from simcore_service_director import config, exceptions, producer
from tenacity import Retrying
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed


@pytest.fixture
def ensure_service_runs_in_ci(monkeypatch):
    monkeypatch.setattr(config, "DEFAULT_MAX_MEMORY", int(25 * pow(1024, 2)))
    monkeypatch.setattr(config, "DEFAULT_MAX_NANO_CPUS", int(0.01 * pow(10, 9)))


@pytest.fixture
async def run_services(
    ensure_service_runs_in_ci,
    aiohttp_mock_app,
    configure_registry_access,
    configure_schemas_location,
    push_services,
    docker_swarm,
    user_id,
    project_id,
    docker_client: docker.client.DockerClient,
) -> Callable:
    started_services = []

    async def push_start_services(number_comp: int, number_dyn: int, dependant=False):
        pushed_services = await push_services(
            number_comp, number_dyn, inter_dependent_services=dependant
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
            with pytest.raises(exceptions.ServiceUUIDNotFoundError):
                await producer.get_service_details(aiohttp_mock_app, service_uuid)
            # start the service
            started_service = await producer.start_service(
                aiohttp_mock_app,
                user_id,
                project_id,
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
            node_details = await producer.get_service_details(
                aiohttp_mock_app, service_uuid
            )
            max_time = 60
            for attempt in Retrying(
                wait=wait_fixed(1), stop=stop_after_delay(max_time), reraise=True
            ):
                with attempt:
                    print(
                        f"--> waiting for {started_service['service_key']}:{started_service['service_version']} to run..."
                    )
                    node_details = await producer.get_service_details(
                        aiohttp_mock_app, service_uuid
                    )
                    print(
                        f"<-- {started_service['service_key']}:{started_service['service_version']} state is {node_details['service_state']} using {config.DEFAULT_MAX_MEMORY}Bytes, {config.DEFAULT_MAX_NANO_CPUS}nanocpus"
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
        await producer.stop_service(aiohttp_mock_app, service_uuid, save_state=False)
        with pytest.raises(exceptions.ServiceUUIDNotFoundError):
            await producer.get_service_details(aiohttp_mock_app, service_uuid)


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
    with pytest.raises(exceptions.ServiceNotAvailableError):
        await producer._find_service_tag(list_of_images, "some_wrong_key", None)
    with pytest.raises(exceptions.ServiceNotAvailableError):
        await producer._find_service_tag(
            list_of_images, my_service_key, "some wrong key"
        )
    # get the latest (e.g. 2.11.0)
    latest_version = await producer._find_service_tag(
        list_of_images, my_service_key, None
    )
    assert latest_version == "2.11.0"
    latest_version = await producer._find_service_tag(
        list_of_images, my_service_key, "latest"
    )
    assert latest_version == "2.11.0"
    # get a specific version
    version = await producer._find_service_tag(list_of_images, my_service_key, "1.2.3")


async def test_start_stop_service(docker_network, run_services):
    # standard test
    await run_services(number_comp=1, number_dyn=1)


async def test_service_assigned_env_variables(
    docker_network, run_services, user_id, project_id
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
        assert envs_dict["SIMCORE_USER_ID"] == user_id
        assert "SIMCORE_NODE_UUID" in envs_dict
        assert envs_dict["SIMCORE_NODE_UUID"] == service_uuid
        assert "SIMCORE_PROJECT_ID" in envs_dict
        assert envs_dict["SIMCORE_PROJECT_ID"] == project_id
        assert "SIMCORE_NODE_BASEPATH" in envs_dict
        assert envs_dict["SIMCORE_NODE_BASEPATH"] == service["service_basepath"]
        assert "SIMCORE_HOST_NAME" in envs_dict
        assert envs_dict["SIMCORE_HOST_NAME"] == docker_service.name

        assert config.MEM_RESOURCE_LIMIT_KEY in envs_dict
        assert config.CPU_RESOURCE_LIMIT_KEY in envs_dict


async def test_interactive_service_published_port(docker_network, run_services):
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


@pytest.fixture
def docker_network(
    docker_client: docker.client.DockerClient, docker_swarm: None
) -> docker.models.networks.Network:
    network = docker_client.networks.create(
        "test_network_default", driver="overlay", scope="swarm"
    )
    print(f"--> docker network '{network.name}' created")
    config.SIMCORE_SERVICES_NETWORK_NAME = network.name
    yield network

    # cleanup
    print(f"<-- removing docker network '{network.name}'...")
    network.remove()

    for attempt in Retrying(stop=stop_after_delay(60), wait=wait_fixed(1)):
        with attempt:
            list_networks = docker_client.networks.list(
                config.SIMCORE_SERVICES_NETWORK_NAME
            )
            assert not list_networks
    config.SIMCORE_SERVICES_NETWORK_NAME = None
    print(f"<-- removed docker network '{network.name}'")


async def test_interactive_service_in_correct_network(
    docker_network: docker.models.networks.Network, run_services
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
            docker_service.attrs["Spec"]["Networks"][0]["Target"] == docker_network.id
        )


async def test_dependent_services_have_common_network(docker_network, run_services):
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
    fake_service: FakeDockerService,
):
    docker_service_partial_inspect = {
        "Spec": {
            "TaskTemplate": {
                "ContainerSpec": {
                    "Image": f"{config.REGISTRY_PATH}{fake_service.service_str}"
                }
            }
        }
    }
    (
        service_key,
        service_tag,
    ) = await producer._get_service_key_version_from_docker_service(
        docker_service_partial_inspect
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
    fake_service_str: str,
):
    docker_service_partial_inspect = {
        "Spec": {
            "TaskTemplate": {
                "ContainerSpec": {
                    "Image": f"{config.REGISTRY_PATH if fake_service_str.startswith('/') else ''}{fake_service_str}"
                }
            }
        }
    }
    with pytest.raises(exceptions.DirectorException):
        await producer._get_service_key_version_from_docker_service(
            docker_service_partial_inspect
        )
