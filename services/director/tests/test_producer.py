# pylint:disable=wildcard-import
# pylint:disable=unused-import
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
import uuid

import pytest

import docker
from simcore_service_director import config, exceptions, producer


@pytest.fixture
async def run_services(loop, configure_registry_access, push_services, docker_swarm, user_id):
    started_services = []
    async def push_start_services(number_comp, number_dyn):
        pushed_services = push_services(number_comp, number_dyn, 60)
        assert len(pushed_services) == (number_comp + number_dyn)
        for pushed_service in pushed_services:
            service_description = pushed_service["service_description"]
            service_key = service_description["key"]
            service_version = service_description["version"]
            service_port = pushed_service["internal_port"]
            service_uuid = str(uuid.uuid1())
            service_basepath = "/my/base/path"
            with pytest.raises(exceptions.ServiceUUIDNotFoundError, message="expecting service uuid not found error"):
                await producer.get_service_details(service_uuid)
            # start the service
            started_service = await producer.start_service(user_id, service_key, service_version, service_uuid, service_basepath)
            assert "published_port" in started_service
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
            # should not throw
            node_details = await producer.get_service_details(service_uuid)
            assert node_details == started_service
            started_services.append(started_service)
        return started_services

    yield push_start_services

    #teardown stop the services
    for service in started_services:
        service_uuid = service["service_uuid"]
        await producer.stop_service(service_uuid)
        with pytest.raises(exceptions.ServiceUUIDNotFoundError, message="expecting service uuid not found error"):
            await producer.get_service_details(service_uuid)


async def test_start_stop_service(run_services):
    # standard test
    await run_services(number_comp=1, number_dyn=1)


async def test_service_assigned_env_variables(run_services, user_id):
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
        assert "SIMCORE_NODE_UUID" in envs_dict
        assert envs_dict["SIMCORE_NODE_UUID"] == service_uuid
        assert "SIMCORE_USER_ID" in envs_dict
        assert envs_dict["SIMCORE_USER_ID"] == user_id
        assert "SIMCORE_NODE_BASEPATH" in envs_dict
        assert envs_dict["SIMCORE_NODE_BASEPATH"] == service["service_basepath"]

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

async def test_extra_hosts_passed_to_services(run_services):
    # would need to test right inside a docker or test from outside...
    # start the director with extra hosts, start some services, and test if the extra hosts are added
    pass