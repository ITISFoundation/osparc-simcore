import uuid

import docker
import pytest
from simcore_service_director import (
    config,
    producer,
    exceptions
)

@pytest.fixture
def run_services(configure_registry_access, push_services, docker_swarm): #pylint: disable=W0613, W0621
    started_services = []
    def push_start_services(number_comp, number_dyn):
        pushed_services = push_services(number_comp,number_dyn, 60)
        assert len(pushed_services) == (number_comp + number_dyn)
        for pushed_service in pushed_services:    
            service_description = pushed_service["service_description"]

            service_key = service_description["key"]
            service_version = service_description["version"]
            service_uuid = str(uuid.uuid4())
            with pytest.raises(exceptions.ServiceUUIDNotFoundError, message="expecting service uuid not found error"):
                producer.get_service_details(service_uuid)
            # start the service
            started_service = producer.start_service(service_key, service_version, service_uuid)
            assert "published_port" in started_service
            assert "entry_point" in started_service
            assert "service_uuid" in started_service    
            # should not throw
            producer.get_service_details(service_uuid)
            started_services.append(started_service)
        return started_services
    yield push_start_services

    #teardown stop the services
    for service in started_services:    
        service_uuid = service["service_uuid"]
        producer.stop_service(service_uuid)
        with pytest.raises(exceptions.ServiceUUIDNotFoundError, message="expecting service uuid not found error"):
            producer.get_service_details(service_uuid)

def test_start_stop_service(run_services): #pylint: disable=W0613, W0621
    # standard test
    run_services(1,1)


def _check_env_variable(envs, variable_name):
    assert variable_name in envs
    assert envs[variable_name] == getattr(config, variable_name)

def test_service_assigned_env_variables(run_services): #pylint: disable=W0621
    started_services = run_services(1,1)
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
        _check_env_variable(envs_dict, "POSTGRES_ENDPOINT")
        _check_env_variable(envs_dict, "POSTGRES_HOST")
        _check_env_variable(envs_dict, "POSTGRES_PORT")
        _check_env_variable(envs_dict, "POSTGRES_USER")
        _check_env_variable(envs_dict, "POSTGRES_PASSWORD")
        _check_env_variable(envs_dict, "POSTGRES_DB")

        _check_env_variable(envs_dict, "S3_ENDPOINT")
        _check_env_variable(envs_dict, "S3_ACCESS_KEY")
        _check_env_variable(envs_dict, "S3_SECRET_KEY")
        _check_env_variable(envs_dict, "S3_BUCKET_NAME")

        assert "SIMCORE_NODE_UUID" in envs_dict
        assert envs_dict["SIMCORE_NODE_UUID"] == service_uuid

def test_interactive_service_published_port(run_services): #pylint: disable=W0621
    running_dynamic_services = run_services(0,1)
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