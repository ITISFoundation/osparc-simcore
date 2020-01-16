# pylint:disable=wildcard-import
# pylint:disable=unused-import
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=too-many-arguments
# pylint:disable=protected-access

import asyncio
import time
import uuid

import docker
import pytest

from simcore_service_director import config, exceptions, producer


@pytest.fixture
async def run_services(aiohttp_mock_app, configure_registry_access, configure_schemas_location, push_services, docker_swarm, user_id, project_id):
    started_services = []
    async def push_start_services(number_comp, number_dyn, dependant=False):
        pushed_services = push_services(number_comp, number_dyn, inter_dependent_services=dependant)
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
            started_service = await producer.start_service(aiohttp_mock_app, user_id, project_id, service_key, service_version, service_uuid, service_basepath)
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
            node_details = await producer.get_service_details(aiohttp_mock_app, service_uuid)
            start_time = time.perf_counter()
            max_time = 2 * 60
            while node_details["service_state"] != "running":
                asyncio.sleep(2)
                if (time.perf_counter() - start_time) > max_time:
                    assert True, "waiting too long to start service"
                node_details = await producer.get_service_details(aiohttp_mock_app, service_uuid)
            started_service["service_state"] = node_details["service_state"]
            started_service["service_message"] = node_details["service_message"]
            assert node_details == started_service
            started_services.append(started_service)
        return started_services

    yield push_start_services

    #teardown stop the services
    for service in started_services:
        service_uuid = service["service_uuid"]
        await producer.stop_service(aiohttp_mock_app, service_uuid)
        with pytest.raises(exceptions.ServiceUUIDNotFoundError):
            await producer.get_service_details(aiohttp_mock_app, service_uuid)

async def test_find_service_tag(loop):
    my_service_key = "myservice-key"
    list_of_images = {my_service_key: ["2.4.0", "2.11.0", "2.8.0", "1.2.1", "some wrong value", "latest", "1.2.0", "1.2.3"]}
    with pytest.raises(exceptions.ServiceNotAvailableError):
        await producer._find_service_tag(list_of_images, "some_wrong_key", None)
    with pytest.raises(exceptions.ServiceNotAvailableError):
        await producer._find_service_tag(list_of_images, my_service_key, "some wrong key")
    # get the latest (e.g. 2.11.0)
    latest_version = await producer._find_service_tag(list_of_images, my_service_key, None)
    assert latest_version == "2.11.0"
    latest_version = await producer._find_service_tag(list_of_images, my_service_key, "latest")
    assert latest_version == "2.11.0"
    # get a specific version
    version = await producer._find_service_tag(list_of_images, my_service_key, "1.2.3")

async def test_start_stop_service(run_services):
    # standard test
    await run_services(number_comp=1, number_dyn=1)


async def test_service_assigned_env_variables(run_services, user_id, project_id):
    started_services = await run_services(number_comp=1, number_dyn=1)
    client = docker.from_env()
    for service in started_services:
        service_uuid = service["service_uuid"]
        list_of_services = client.services.list(filters={"label":"uuid=" + service_uuid})
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

async def test_interactive_service_published_port(run_services):
    running_dynamic_services = await run_services(number_comp=0, number_dyn=1)
    assert len(running_dynamic_services) == 1

    service = running_dynamic_services[0]
    assert "published_port" in service

    service_port = service["published_port"]
    # ports are not published anymore in production mode
    assert not service_port

    client = docker.from_env()
    service_uuid = service["service_uuid"]
    list_of_services = client.services.list(filters={"label":"uuid=" + service_uuid})
    assert len(list_of_services) == 1

    docker_service = list_of_services[0]
    # no port open to the outside
    assert not docker_service.attrs["Endpoint"]["Spec"]
    # service is started with dnsrr (round-robin) mode
    assert docker_service.attrs["Spec"]["EndpointSpec"]["Mode"] == "dnsrr"


@pytest.fixture
def docker_network(docker_swarm) -> docker.models.networks.Network:
    client = docker_swarm
    network = client.networks.create("test_network", driver="overlay", scope="swarm")
    config.SIMCORE_SERVICES_NETWORK_NAME = network.name
    yield network

    # cleanup
    network.remove()
    config.SIMCORE_SERVICES_NETWORK_NAME = None


async def test_interactive_service_in_correct_network(docker_network, run_services):

    running_dynamic_services = await run_services(number_comp=0, number_dyn=2, dependant=False)
    assert len(running_dynamic_services) == 2
    for service in running_dynamic_services:
        client = docker.from_env()
        service_uuid = service["service_uuid"]
        list_of_services = client.services.list(filters={"label":"uuid=" + service_uuid})
        assert list_of_services
        assert len(list_of_services) == 1
        docker_service = list_of_services[0]
        assert docker_service.attrs["Spec"]["Networks"][0]["Target"] == docker_network.id



async def test_dependent_services_have_common_network(run_services):
    running_dynamic_services = await run_services(number_comp=0, number_dyn=2, dependant=True)
    assert len(running_dynamic_services) == 2

    for service in running_dynamic_services:
        client = docker.from_env()
        service_uuid = service["service_uuid"]
        list_of_services = client.services.list(filters={"label":"uuid=" + service_uuid})
        # there is one dependency per service
        assert len(list_of_services) == 2
        # check they have same network
        assert list_of_services[0].attrs["Spec"]["Networks"][0]["Target"] == \
            list_of_services[1].attrs["Spec"]["Networks"][0]["Target"]
