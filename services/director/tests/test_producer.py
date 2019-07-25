# pylint:disable=wildcard-import
# pylint:disable=unused-import
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=too-many-arguments

import asyncio
import time
import uuid

import docker
import pytest

from simcore_service_director import config, exceptions, producer


@pytest.fixture
async def aiohttp_mock_app(loop, mocker):
    aiohttp_app = mocker.patch('aiohttp.web.Application')
    return aiohttp_mock_app

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
            service_uuid = str(uuid.uuid1())
            service_basepath = "/my/base/path"
            with pytest.raises(exceptions.ServiceUUIDNotFoundError):
                await producer.get_service_details(aiohttp_mock_app, service_uuid)
            # start the service
            started_service = await producer.start_service(aiohttp_mock_app, user_id, project_id, service_key, service_version, service_uuid, service_basepath)
            assert "published_port" in started_service
            if service_description["type"] == "dynamic":
                assert started_service["published_port"]
            assert "entry_point" in started_service
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
        envs_dict = {key:value for key,value in (x.split("=") for x in envs_list)}

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
    assert service_port > 0

    client = docker.from_env()
    service_uuid = service["service_uuid"]
    list_of_services = client.services.list(filters={"label":"uuid=" + service_uuid})
    assert len(list_of_services) == 1

    docker_service = list_of_services[0]
    low_level_client = docker.APIClient()
    service_information = low_level_client.inspect_service(docker_service.id)
    service_published_port = service_information["Endpoint"]["Ports"][0]["PublishedPort"]
    assert service_published_port == service_port

async def test_dependent_services_have_common_network(run_services):
    running_dynamic_services = await run_services(number_comp=0, number_dyn=2, dependant=True)
    assert len(running_dynamic_services) == 2

    for service in running_dynamic_services:
        client = docker.from_env()
        service_uuid = service["service_uuid"]
        list_of_services = client.services.list(filters={"label":"uuid=" + service_uuid})
        # there is one dependency per service
        assert len(list_of_services) == 2

@pytest.mark.skip(reason="needs a real registry for testing auth")
async def test_authentication(aiohttp_mock_app, docker_swarm):
    #this needs to be filled up
    config.REGISTRY_URL = ""
    config.REGISTRY_USER = ""
    config.REGISTRY_PW = ""
    config.REGISTRY_SSL = True
    config.REGISTRY_AUTH = True
    service = await producer.start_service(aiohttp_mock_app, "someuser", "project", "simcore/services/comp/itis/sleeper", "latest", "node", None)

@pytest.mark.skip(reason="slow test and not necessary to repeat")
async def test_performance_async(aiohttp_mock_app, configure_registry_access, configure_schemas_location, push_services, docker_swarm, user_id, project_id):
    number_of_services = 1
    pushed_services = push_services(number_of_services, number_of_services, inter_dependent_services=False)
    assert len(pushed_services) == 2 * number_of_services

    for pushed_service in pushed_services:
        service_description = pushed_service["service_description"]
        service_key = service_description["key"]
        service_version = service_description["version"]
        service_port = pushed_service["internal_port"]
        service_basepath = "/my/base/path"
        # start the service
        for i in range(10):
            service_uuid = str(uuid.uuid1())
            with pytest.raises(exceptions.ServiceUUIDNotFoundError):
                await producer.get_service_details(aiohttp_mock_app, service_uuid)
            started_service = await producer.start_service(aiohttp_mock_app, user_id, project_id, service_key, service_version, service_uuid, service_basepath)

@pytest.mark.skip(reason="slow test and not necessary to repeat")
async def test_performance_pure_docker_api_calls(aiohttp_mock_app, configure_registry_access, docker_registry, configure_schemas_location, push_services, docker_swarm, user_id, project_id):
    number_of_services = 1
    pushed_services = push_services(number_of_services, number_of_services, inter_dependent_services=False)
    assert len(pushed_services) == 2 * number_of_services

    client = docker.from_env()
    low_level_client = docker.APIClient()
    for pushed_service in pushed_services:
        service_description = pushed_service["service_description"]
        service_key = service_description["key"]
        service_version = service_description["version"]
        service_port = pushed_service["internal_port"]
        service_basepath = "/my/base/path"
        # start the service
        for i in range(10):
            service_uuid = str(uuid.uuid1())
            with pytest.raises(exceptions.ServiceUUIDNotFoundError):
                await producer.get_service_details(aiohttp_mock_app, service_uuid)
            started_service = client.services.create("{}/{}:{}".format(docker_registry, service_key, service_version))
            # wait for the task to start
            while True:
                tasks = started_service.tasks()
                if tasks:
                    last_task = tasks[0]
                    task_state = last_task["Status"]["State"]
                    if task_state in ("failed", "rejected"):
                        assert True, "task failed"
                    if task_state in ("running", "complete"):
                        break
                await asyncio.sleep(1)  # 1s
