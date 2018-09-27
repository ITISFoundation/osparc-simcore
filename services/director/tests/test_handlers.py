import json
import uuid
from pathlib import Path

import pytest
from aiohttp import web_exceptions
from simcore_service_director import config, rest

from helpers import json_schema_validator


@pytest.mark.asyncio
async def test_root_get():
    fake_request = "fake request"
    response = await rest.handlers.root_get(fake_request)
    assert "data" in response
    assert "status" in response
    assert response["status"] == 200

    healthcheck_enveloped = rest.models.HealthCheckEnveloped.from_dict(response)
    assert healthcheck_enveloped.status == 200
    assert isinstance(healthcheck_enveloped.data, rest.models.HealthCheck)

    healthcheck = healthcheck_enveloped.data
    assert healthcheck.name == "simcore-service-director"
    assert healthcheck.status == "SERVICE_RUNNING"
    assert healthcheck.version == "0.1.0"
    assert healthcheck.api_version == "1.0.0"

def _check_services(created_services, services, schema_version="v1"):
    assert len(created_services) == len(services)

    created_service_descriptions = [x["service_description"] for x in created_services]
    
    # TODO: use resources!
    json_schema_path = Path(__file__).parent.parent / "src/simcore_service_director/oas3/v1/schemas/node-meta-v0.0.1.json"
    assert json_schema_path.exists() == True
    with json_schema_path.open() as file_pt:
        service_schema = json.load(file_pt)

    for service in services:
        assert isinstance(service, rest.models.NodeMetaV0)
        if schema_version == "v1":
            assert created_service_descriptions.count(service.to_dict()) == 1
        json_schema_validator.validate_instance_object(service.to_dict(), service_schema)

@pytest.mark.asyncio
async def test_services_get(docker_registry, push_services):
    config.CONVERT_OLD_API = False
    fake_request = "fake request"
    # no registry defined
    with pytest.raises(web_exceptions.HTTPInternalServerError, message="Expecting HTTP Internal Error as no registry URL is defined"):
        services_enveloped = rest.models.ServicesEnveloped.from_dict(await rest.handlers.services_get(fake_request))

    # wrong registry defined
    config.REGISTRY_URL = "blahblah" 
    with pytest.raises(web_exceptions.HTTPInternalServerError, message="Expecting HTTP Internal Error as SSL is enabled by default"):
        services_enveloped = rest.models.ServicesEnveloped.from_dict(await rest.handlers.services_get(fake_request))
    
    # right registry defined
    config.REGISTRY_URL = docker_registry
    with pytest.raises(web_exceptions.HTTPInternalServerError, message="Expecting HTTP Internal Error as SSL is enabled by default"):
        services_enveloped = rest.models.ServicesEnveloped.from_dict(await rest.handlers.services_get(fake_request))

    # no SSL
    config.REGISTRY_SSL = False
    # empty case
    services_enveloped = rest.models.ServicesEnveloped.from_dict(await rest.handlers.services_get(fake_request))
    assert services_enveloped.status == 200
    assert isinstance(services_enveloped.data, list)
    services = services_enveloped.data
    _check_services([], services)

    # some services
    created_services = push_services(3,2)
    services_enveloped = rest.models.ServicesEnveloped.from_dict(await rest.handlers.services_get(fake_request))
    assert services_enveloped.status == 200
    assert isinstance(services_enveloped.data, list)
    services = services_enveloped.data
    _check_services(created_services, services)

@pytest.mark.asyncio
async def test_v0_services_conversion_to_new(configure_registry_access, push_v0_schema_services): #pylint: disable=W0613, W0621
    fake_request = "fake request"
    created_services = push_v0_schema_services(3,2)
    assert len(created_services) == 5
    services_enveloped = rest.models.ServicesEnveloped.from_dict(await rest.handlers.services_get(fake_request))
    assert services_enveloped.status == 200
    assert isinstance(services_enveloped.data, list)
    services = services_enveloped.data
    # ensure old style services are not retrieved
    assert len(services) == 0

    # check conversion
    config.CONVERT_OLD_API = True
    services_enveloped = rest.models.ServicesEnveloped.from_dict(await rest.handlers.services_get(fake_request))
    assert services_enveloped.status == 200
    assert isinstance(services_enveloped.data, list)
    services = services_enveloped.data
    _check_services(created_services, services, "v0")

@pytest.mark.asyncio
async def test_v1_services_with_old_conversion(configure_registry_access, push_services): #pylint: disable=W0613, W0621
    fake_request = "fake request"
    created_services = push_services(3,2)
    assert len(created_services) == 5
    # no conversion, shoult return the exact same services    
    services_enveloped = rest.models.ServicesEnveloped.from_dict(await rest.handlers.services_get(fake_request))
    assert services_enveloped.status == 200
    assert isinstance(services_enveloped.data, list)
    services = services_enveloped.data
    _check_services(created_services, services)

    # with conversion enabled, should return no services
    config.CONVERT_OLD_API = True
    services_enveloped = rest.models.ServicesEnveloped.from_dict(await rest.handlers.services_get(fake_request))
    assert services_enveloped.status == 200
    assert isinstance(services_enveloped.data, list)
    services = services_enveloped.data
    assert len(services) == 0


@pytest.mark.asyncio
async def test_services_by_key_version_get(configure_registry_access, push_services): #pylint: disable=W0613, W0621
    fake_request = "fake request"
    created_services = push_services(3,2)
    assert len(created_services) == 5
    retrieved_services = []
    for created_service in created_services:
        service_description = created_service["service_description"]
        services_enveloped = rest.models.ServicesEnveloped.from_dict(await rest.handlers.services_by_key_version_get(fake_request, service_description["key"], service_description["version"]))
        assert services_enveloped.status == 200
        assert isinstance(services_enveloped.data, list)
        services = services_enveloped.data
        assert len(services) == 1
        retrieved_services.append(services[0])
    _check_services(created_services, retrieved_services)

async def _start_get_stop_services(push_services):
    fake_request = "fake request"
    created_services = push_services(0,2)
    assert len(created_services) == 2
    for created_service in created_services:
        service_description = created_service["service_description"]
        service_key = service_description["key"]
        service_tag = service_description["version"]
        service_uuid = str(uuid.uuid4())
        # start the service
        running_service_enveloped = rest.models.RunningServiceEnveloped.from_dict(await rest.handlers.running_interactive_services_post(fake_request, service_key, service_uuid, service_tag))
        assert running_service_enveloped.status == 201
        assert isinstance(running_service_enveloped.data, rest.models.RunningService)

        # get the service
        response = rest.models.Response204Enveloped.from_dict(await rest.handlers.running_interactive_services_get(fake_request, service_uuid))
        assert response.status == 204
        assert response.data is None

        # stop the service
        response = rest.models.Response204Enveloped.from_dict(await rest.handlers.running_interactive_services_delete(fake_request, service_uuid))
        assert response.status == 204
        assert response.data is None

@pytest.mark.asyncio
async def test_running_services_post_and_delete_no_swarm(configure_registry_access, push_services): #pylint: disable=W0613, W0621
    with pytest.raises(web_exceptions.HTTPInternalServerError, message="Expecting internal error as there is no docker swarm"):
        await _start_get_stop_services(push_services)

@pytest.mark.asyncio
async def test_running_services_post_and_delete(configure_registry_access, push_services, docker_swarm): #pylint: disable=W0613, W0621
    await _start_get_stop_services(push_services)
