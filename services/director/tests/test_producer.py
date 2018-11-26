import uuid

import docker
import pytest
from simcore_service_director import (
    producer,
    exceptions
)

@pytest.fixture
async def run_services(loop, configure_registry_access, push_services, docker_swarm, user_id): #pylint: disable=W0613, W0621
    started_services = []
    async def push_start_services(number_comp, number_dyn):
        pushed_services = push_services(number_comp,number_dyn, 60)
        assert len(pushed_services) == (number_comp + number_dyn)
        for pushed_service in pushed_services:
            service_description = pushed_service["service_description"]

            service_key = service_description["key"]
            service_version = service_description["version"]
            service_uuid = str(uuid.uuid4())
            with pytest.raises(exceptions.ServiceUUIDNotFoundError, message="expecting service uuid not found error"):
                await producer.get_service_details(service_uuid)
            # start the service
            started_service = await producer.start_service(user_id, service_key, service_version, service_uuid)
            assert "published_port" in started_service
            assert "entry_point" in started_service
            assert "service_uuid" in started_service
            # should not throw
            await producer.get_service_details(service_uuid)
            started_services.append(started_service)
        return started_services

    yield push_start_services

    #teardown stop the services
    for service in started_services:
        service_uuid = service["service_uuid"]
        await producer.stop_service(service_uuid)
        with pytest.raises(exceptions.ServiceUUIDNotFoundError, message="expecting service uuid not found error"):
            await producer.get_service_details(service_uuid)


async def test_start_stop_service(run_services): #pylint: disable=W0613, W0621
    # standard test
    await run_services(1,1)


async def test_service_assigned_env_variables(run_services, user_id): #pylint: disable=W0621
    started_services = await run_services(1,1)
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
        assert "SIMCORE_NODE_UUID" in envs_dict
        assert envs_dict["SIMCORE_NODE_UUID"] == service_uuid
        assert "SIMCORE_USER_ID" in envs_dict
        assert envs_dict["SIMCORE_USER_ID"] == user_id


async def test_interactive_service_published_port(run_services): #pylint: disable=W0621
    running_dynamic_services = await run_services(0,1)
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
