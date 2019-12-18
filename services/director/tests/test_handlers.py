# pylint: disable=unused-argument
# pylint: disable=unused-import
# pylint: disable=bare-except
# pylint: disable=redefined-outer-name
# pylint: disable=R0915
# pylint: disable=too-many-arguments

import json
import uuid
from urllib.parse import quote

import pytest
from aiohttp import web, web_exceptions

from helpers import json_schema_validator
from servicelib.rest_responses import unwrap_envelope
from simcore_service_director import config, main, resources, rest

API_VERSIONS = resources.listdir(resources.RESOURCE_OPENAPI_ROOT)

@pytest.fixture
def client(loop, aiohttp_client, aiohttp_unused_port, configure_schemas_location, configure_registry_access):
    app = main.setup_app()
    server_kwargs={'port': aiohttp_unused_port(), 'host': 'localhost'}
    client = loop.run_until_complete(aiohttp_client(app, server_kwargs=server_kwargs))
    return client

async def test_root_get(loop, client):
    web_response = await client.get("/v0/")
    assert web_response.content_type == "application/json"
    assert web_response.status == 200
    healthcheck_enveloped = await web_response.json()
    assert "data" in healthcheck_enveloped

    assert isinstance(healthcheck_enveloped["data"], dict)

    healthcheck = healthcheck_enveloped["data"]
    assert healthcheck["name"] == "simcore-service-director"
    assert healthcheck["status"] == "SERVICE_RUNNING"
    assert healthcheck["version"] == "0.1.0"
    assert healthcheck["api_version"] == "0.1.0"

def _check_services(created_services, services, schema_version="v1"):
    assert len(created_services) == len(services)

    created_service_descriptions = [x["service_description"] for x in created_services]

    json_schema_path = resources.get_path(resources.RESOURCE_NODE_SCHEMA)
    assert json_schema_path.exists() == True
    with json_schema_path.open() as file_pt:
        service_schema = json.load(file_pt)

    for service in services:
        if schema_version == "v1":
            assert created_service_descriptions.count(service) == 1
        json_schema_validator.validate_instance_object(service, service_schema)


async def test_services_get(docker_registry, client, push_services):
    # empty case
    web_response = await client.get("/v0/services")
    assert web_response.status == 200
    assert web_response.content_type == "application/json"
    services_enveloped = await web_response.json()
    assert isinstance(services_enveloped["data"], list)
    services = services_enveloped["data"]
    _check_services([], services)

    # some services
    created_services = push_services(3,2)
    web_response = await client.get("/v0/services")
    assert web_response.status == 200
    assert web_response.content_type == "application/json"
    services_enveloped = await web_response.json()
    assert isinstance(services_enveloped["data"], list)
    services = services_enveloped["data"]
    _check_services(created_services, services)

    web_response = await client.get("/v0/services?service_type=blahblah")
    assert web_response.status == 400
    assert web_response.content_type == "application/json"
    services_enveloped = await web_response.json()
    assert not "data" in services_enveloped
    assert "error" in services_enveloped

    web_response = await client.get("/v0/services?service_type=computational")
    assert web_response.status == 200
    assert web_response.content_type == "application/json"
    services_enveloped = await web_response.json()
    assert isinstance(services_enveloped["data"], list)
    services = services_enveloped["data"]
    assert len(services) == 3

    web_response = await client.get("/v0/services?service_type=interactive")
    assert web_response.status == 200
    assert web_response.content_type == "application/json"
    services_enveloped = await web_response.json()
    assert isinstance(services_enveloped["data"], list)
    services = services_enveloped["data"]
    assert len(services) == 2


async def test_services_by_key_version_get(client, push_services): #pylint: disable=W0613, W0621
    web_response = await client.get("/v0/services/whatever/someversion")
    assert web_response.status == 400
    web_response = await client.get("/v0/services/simcore/services/dynamic/something/someversion")
    assert web_response.status == 404
    web_response = await client.get("/v0/services/simcore/services/dynamic/something/1.5.2")
    assert web_response.status == 404

    created_services = push_services(3,2)
    assert len(created_services) == 5

    retrieved_services = []
    for created_service in created_services:
        service_description = created_service["service_description"]
        # note that it is very important to remove the safe="/" from quote!!!!
        url = "/v0/services/{}/{}".format(quote(service_description["key"], safe=""), quote(service_description["version"], safe=""))
        web_response = await client.get(url)

        assert web_response.status == 200, await web_response.text() #here the error is actually json.
        assert web_response.content_type == "application/json"
        services_enveloped = await web_response.json()

        assert isinstance(services_enveloped["data"], list)
        services = services_enveloped["data"]
        assert len(services) == 1
        retrieved_services.append(services[0])
    _check_services(created_services, retrieved_services)

async def _start_get_stop_services(client, push_services, user_id, project_id):
    params = {}
    web_response = await client.post("/v0/running_interactive_services", params=params)
    assert web_response.status == 400

    params = {
        "user_id": "None",
        "project_id": "None",
        "service_uuid": "sdlfkj4",
        "service_key": "None",
        "service_tag": "None", # optional
        "service_basepath": "None" #optional
    }
    web_response = await client.post("/v0/running_interactive_services", params=params)
    data = await web_response.json()
    assert web_response.status == 400, data

    params["service_key"] = "simcore/services/comp/somfunkyname-nhsd"
    params["service_tag"] = "1.2.3"
    web_response = await client.post("/v0/running_interactive_services", params=params)
    data = await web_response.json()
    assert web_response.status == 404, data

    created_services = push_services(0,2)
    assert len(created_services) == 2
    for created_service in created_services:
        service_description = created_service["service_description"]
        params["user_id"] = user_id
        params["project_id"] = project_id
        params["service_key"] = service_description["key"]
        params["service_tag"] = service_description["version"]
        service_port = created_service["internal_port"]
        service_entry_point = created_service["entry_point"]
        params["service_basepath"] = "/i/am/a/basepath"
        params["service_uuid"] = str(uuid.uuid4())
        # start the service
        web_response = await client.post("/v0/running_interactive_services", params=params)
        assert web_response.status == 201
        assert web_response.content_type == "application/json"
        running_service_enveloped = await web_response.json()
        assert isinstance(running_service_enveloped["data"], dict)
        assert all(k in running_service_enveloped["data"] for k in ["service_uuid", "service_key", "service_version", "published_port", "entry_point", "service_host", "service_port", "service_basepath"])
        assert running_service_enveloped["data"]["service_uuid"] == params["service_uuid"]
        assert running_service_enveloped["data"]["service_key"] == params["service_key"]
        assert running_service_enveloped["data"]["service_version"] == params["service_tag"]
        assert running_service_enveloped["data"]["service_port"] == service_port
        service_published_port = running_service_enveloped["data"]["published_port"]
        assert not service_published_port
        assert service_entry_point == running_service_enveloped["data"]["entry_point"]
        service_host = running_service_enveloped["data"]["service_host"]
        assert service_host == "test_{}".format(params["service_uuid"])
        service_basepath = running_service_enveloped["data"]["service_basepath"]
        assert service_basepath == params["service_basepath"]


        # get the service
        web_response = await client.request("GET", "/v0/running_interactive_services/{}".format(params["service_uuid"]))
        assert web_response.status == 200
        text = await web_response.text()
        assert web_response.content_type == "application/json", text
        running_service_enveloped = await web_response.json()
        assert isinstance(running_service_enveloped["data"], dict)
        assert all(k in running_service_enveloped["data"] for k in ["service_uuid", "service_key", "service_version", "published_port", "entry_point"])
        assert running_service_enveloped["data"]["service_uuid"] == params["service_uuid"]
        assert running_service_enveloped["data"]["service_key"] == params["service_key"]
        assert running_service_enveloped["data"]["service_version"] == params["service_tag"]
        assert running_service_enveloped["data"]["published_port"] == service_published_port
        assert running_service_enveloped["data"]["entry_point"] == service_entry_point
        assert running_service_enveloped["data"]["service_host"] == service_host
        assert running_service_enveloped["data"]["service_port"] == service_port
        assert running_service_enveloped["data"]["service_basepath"] == service_basepath

        # stop the service
        web_response = await client.delete("/v0/running_interactive_services/{}".format(params["service_uuid"]))
        text = await web_response.text()
        assert web_response.status == 204, text
        assert web_response.content_type == "application/json"
        data = await web_response.json()
        assert data is None

@pytest.mark.skip(reason="docker_swarm fixture is a session fixture making it bad running together with other tests that require a swarm")
async def test_running_services_post_and_delete_no_swarm(client, push_services, user_id, project_id): #pylint: disable=W0613, W0621
    params = {
        "user_id": "None",
        "project_id": "None",
        "service_uuid": "sdlfkj4",
        "service_key": "simcore/services/comp/some-key"
    }
    web_response = await client.post("/v0/running_interactive_services", params=params)
    data = await web_response.json()
    assert web_response.status == 500, data

async def test_running_services_post_and_delete(client, push_services, docker_swarm, user_id, project_id): #pylint: disable=W0613, W0621
    await _start_get_stop_services(client, push_services, user_id, project_id)


async def test_running_interactive_services_list_get(client, push_services, docker_swarm):
    """Test case for running_interactive_services_list_get

    Returns a list of interactive services
    """
    user_ids = ["first_user_id", "second_user_id"]
    project_ids = ["first_project_id", "second_project_id", "third_project_id"]
    # prepare services
    NUM_SERVICES = 1
    created_services = push_services(0,NUM_SERVICES)
    assert len(created_services) == NUM_SERVICES
    # start the services
    for user_id in user_ids:
        for project_id in project_ids:
            for created_service in created_services:
                service_description = created_service["service_description"]
                params = {}
                params["user_id"] = user_id
                params["project_id"] = project_id
                params["service_key"] = service_description["key"]
                params["service_tag"] = service_description["version"]
                params["service_uuid"] = str(uuid.uuid4())
                # start the service
                web_response = await client.post("/v0/running_interactive_services", params=params)
                assert web_response.status == 201
    # get the list of services
    for user_id in user_ids:
        for project_id in project_ids:
            params = {}
            # list by user_id
            params["user_id"] = user_id
            response = await client.get(path='/v0/running_interactive_services', params=params)
            assert response.status == 200, 'Response body is : ' + (await response.read()).decode('utf-8')
            data, error = unwrap_envelope(await response.json())
            assert data
            assert not error
            services_list = data
            assert len(services_list) == len(project_ids) * NUM_SERVICES
            # list by user_id and project_id
            params["project_id"] = project_id
            response = await client.get(path='/v0/running_interactive_services', params=params)
            assert response.status == 200, 'Response body is : ' + (await response.read()).decode('utf-8')
            data, error = unwrap_envelope(await response.json())
            assert data
            assert not error
            services_list = data
            assert len(services_list) == NUM_SERVICES
            # list by project_id
            params = {}
            params["project_id"] = project_id
            response = await client.get(path='/v0/running_interactive_services', params=params)
            assert response.status == 200, 'Response body is : ' + (await response.read()).decode('utf-8')
            data, error = unwrap_envelope(await response.json())
            assert data
            assert not error
            services_list = data
            assert len(services_list) == len(user_ids) * NUM_SERVICES


@pytest.mark.skip(reason="test needs credentials to real registry")
async def test_performance_get_services(loop, configure_custom_registry, configure_schemas_location):
    import time
    fake_request = "fake request"
    start_time = time.perf_counter()
    number_of_calls = 1
    number_of_services = 0
    for i in range(number_of_calls):
        print("calling iteration", i)
        start_time_i = time.perf_counter()
        web_response = await rest.handlers.services_get(fake_request)
        assert web_response.status == 200
        assert web_response.content_type == "application/json"
        services_enveloped = json.loads(web_response.text)
        assert isinstance(services_enveloped["data"], list)
        services = services_enveloped["data"]
        number_of_services = len(services)
        print("iteration completed in", (time.perf_counter() - start_time_i), "s")
    stop_time = time.perf_counter()
    print("Time to run {} times: {}s, #services {}, time per call {}s/service"
    .format(number_of_calls,
        stop_time-start_time,
        number_of_services,
        (stop_time-start_time)/number_of_calls/number_of_services))
