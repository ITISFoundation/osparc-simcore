# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import uuid

import httpx
import pytest
import respx
from faker import Faker
from fastapi import status
from models_library.projects import ProjectID
from models_library.users import UserID
from pytest_simcore.helpers.typing_env import EnvVarsDict


def _assert_response_and_unwrap_envelope(got: httpx.Response):
    assert got.headers["content-type"] == "application/json"
    assert got.encoding == "utf-8"

    body = got.json()
    assert isinstance(body, dict)
    assert "data" in body or "error" in body
    return body.get("data"), body.get("error")


@pytest.mark.parametrize(
    "save_state, expected_save_state_call", [(True, True), (False, False), (None, True)]
)
async def test_running_services_post_and_delete(
    configure_swarm_stack_name: EnvVarsDict,
    configure_registry_access: EnvVarsDict,
    configured_docker_network: EnvVarsDict,
    client: httpx.AsyncClient,
    push_services,
    user_id: UserID,
    project_id: ProjectID,
    api_version_prefix: str,
    save_state: bool | None,
    expected_save_state_call: bool,
    mocker,
    faker: Faker,
    x_simcore_user_agent_header: dict[str, str],
    ensure_run_in_sequence_context_is_empty: None,
):
    params = {}
    resp = await client.post(
        f"/{api_version_prefix}/running_interactive_services", params=params
    )
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    params = {
        "user_id": f"{faker.pyint(min_value=1)}",
        "project_id": f"{faker.uuid4()}",
        "service_uuid": f"{faker.uuid4()}",
        "service_key": "None",
        "service_tag": "None",  # optional
        "service_basepath": "None",  # optional
    }
    resp = await client.post(
        f"/{api_version_prefix}/running_interactive_services", params=params
    )
    data = resp.json()
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY, data

    params["service_key"] = "simcore/services/comp/somfunkyname-nhsd"
    params["service_tag"] = "1.2.3"
    resp = await client.post(
        f"/{api_version_prefix}/running_interactive_services",
        params=params,
        headers=x_simcore_user_agent_header,
    )
    data = resp.json()
    assert resp.status_code == status.HTTP_404_NOT_FOUND, data

    created_services = await push_services(
        number_of_computational_services=0, number_of_interactive_services=2
    )
    assert len(created_services) == 2
    for created_service in created_services:
        service_description = created_service["service_description"]
        params["user_id"] = f"{user_id}"
        params["project_id"] = f"{project_id}"
        params["service_key"] = service_description["key"]
        params["service_tag"] = service_description["version"]
        service_port = created_service["internal_port"]
        service_entry_point = created_service["entry_point"]
        params["service_basepath"] = "/i/am/a/basepath"
        params["service_uuid"] = f"{faker.uuid4()}"
        # start the service
        resp = await client.post(
            f"/{api_version_prefix}/running_interactive_services",
            params=params,
            headers=x_simcore_user_agent_header,
        )
        assert resp.status_code == status.HTTP_201_CREATED, resp.text
        assert resp.encoding == "utf-8"
        assert resp.headers["content-type"] == "application/json"
        running_service_enveloped = resp.json()
        assert isinstance(running_service_enveloped["data"], dict)
        assert all(
            k in running_service_enveloped["data"]
            for k in [
                "service_uuid",
                "service_key",
                "service_version",
                "published_port",
                "entry_point",
                "service_host",
                "service_port",
                "service_basepath",
            ]
        )
        assert (
            running_service_enveloped["data"]["service_uuid"] == params["service_uuid"]
        )
        assert running_service_enveloped["data"]["service_key"] == params["service_key"]
        assert (
            running_service_enveloped["data"]["service_version"]
            == params["service_tag"]
        )
        assert running_service_enveloped["data"]["service_port"] == service_port
        service_published_port = running_service_enveloped["data"]["published_port"]
        assert not service_published_port
        assert service_entry_point == running_service_enveloped["data"]["entry_point"]
        service_host = running_service_enveloped["data"]["service_host"]
        assert service_host == f"test_{params['service_uuid']}"
        service_basepath = running_service_enveloped["data"]["service_basepath"]
        assert service_basepath == params["service_basepath"]

        # get the service
        resp = await client.request(
            "GET",
            f"/{api_version_prefix}/running_interactive_services/{params['service_uuid']}",
        )
        assert resp.status_code == status.HTTP_200_OK
        text = resp.text
        assert resp.headers["content-type"] == "application/json"
        assert resp.encoding == "utf-8", f"Got {text=}"
        running_service_enveloped = resp.json()
        assert isinstance(running_service_enveloped["data"], dict)
        assert all(
            k in running_service_enveloped["data"]
            for k in [
                "service_uuid",
                "service_key",
                "service_version",
                "published_port",
                "entry_point",
            ]
        )
        assert (
            running_service_enveloped["data"]["service_uuid"] == params["service_uuid"]
        )
        assert running_service_enveloped["data"]["service_key"] == params["service_key"]
        assert (
            running_service_enveloped["data"]["service_version"]
            == params["service_tag"]
        )
        assert (
            running_service_enveloped["data"]["published_port"]
            == service_published_port
        )
        assert running_service_enveloped["data"]["entry_point"] == service_entry_point
        assert running_service_enveloped["data"]["service_host"] == service_host
        assert running_service_enveloped["data"]["service_port"] == service_port
        assert running_service_enveloped["data"]["service_basepath"] == service_basepath

        # stop the service
        query_params = {}
        if save_state:
            query_params.update({"save_state": "true" if save_state else "false"})

        with respx.mock(
            base_url=f"http://{service_host}:{service_port}{service_basepath}",
            assert_all_called=False,
            assert_all_mocked=False,
        ) as respx_mock:

            def _save_me(request) -> httpx.Response:
                return httpx.Response(status.HTTP_200_OK, json={})

            respx_mock.post("/state", name="save_state").mock(side_effect=_save_me)
            respx_mock.route(host="127.0.0.1", name="host").pass_through()
            respx_mock.route(host="localhost", name="localhost").pass_through()

            resp = await client.delete(
                f"/{api_version_prefix}/running_interactive_services/{params['service_uuid']}",
                params=query_params,
            )

        text = resp.text
        assert resp.status_code == status.HTTP_204_NO_CONTENT, text
        assert resp.headers["content-type"] == "application/json"
        assert resp.encoding == "utf-8"


async def test_running_interactive_services_list_get(
    configure_swarm_stack_name: EnvVarsDict,
    configure_registry_access: EnvVarsDict,
    configured_docker_network: EnvVarsDict,
    client: httpx.AsyncClient,
    push_services,
    x_simcore_user_agent_header: dict[str, str],
    api_version_prefix: str,
    ensure_run_in_sequence_context_is_empty: None,
    faker: Faker,
):
    """Test case for running_interactive_services_list_get

    Returns a list of interactive services
    """
    user_ids = [faker.pyint(min_value=1), faker.pyint(min_value=1)]
    project_ids = [faker.uuid4(), faker.uuid4(), faker.uuid4()]
    # prepare services
    NUM_SERVICES = 1
    available_services = await push_services(
        number_of_computational_services=0, number_of_interactive_services=NUM_SERVICES
    )
    assert len(available_services) == NUM_SERVICES
    # start the services
    created_services = []
    for user_id in user_ids:
        for project_id in project_ids:
            for created_service in available_services:
                service_description = created_service["service_description"]
                params = {}
                params["user_id"] = user_id
                params["project_id"] = project_id
                params["service_key"] = service_description["key"]
                params["service_tag"] = service_description["version"]
                params["service_uuid"] = str(uuid.uuid4())
                # start the service
                resp = await client.post(
                    "/v0/running_interactive_services",
                    params=params,
                    headers=x_simcore_user_agent_header,
                )
                assert resp.status_code == 201, resp.text
                created_services.append(resp.json()["data"])
    # get the list of services
    for user_id in user_ids:
        for project_id in project_ids:
            params = {}
            # list by user_id
            params["user_id"] = user_id
            response = await client.get(
                "/v0/running_interactive_services", params=params
            )
            assert (
                response.status_code == status.HTTP_200_OK
            ), f"Response body is : {response.text}"
            data, error = _assert_response_and_unwrap_envelope(response)
            assert data
            assert not error
            services_list = data
            assert len(services_list) == len(project_ids) * NUM_SERVICES
            # list by user_id and project_id
            params["project_id"] = project_id
            response = await client.get(
                "/v0/running_interactive_services", params=params
            )
            assert (
                response.status_code == status.HTTP_200_OK
            ), f"Response body is : {response.text}"
            data, error = _assert_response_and_unwrap_envelope(response)
            assert data
            assert not error
            services_list = data
            assert len(services_list) == NUM_SERVICES
            # list by project_id
            params = {}
            params["project_id"] = project_id
            response = await client.get(
                "/v0/running_interactive_services", params=params
            )
            assert (
                response.status_code == status.HTTP_200_OK
            ), f"Response body is : {response.text}"
            data, error = _assert_response_and_unwrap_envelope(response)
            assert data
            assert not error
            services_list = data
            assert len(services_list) == len(user_ids) * NUM_SERVICES
    # get all the running services
    response = await client.get("/v0/running_interactive_services")
    assert (
        response.status_code == status.HTTP_200_OK
    ), f"Response body is : {response.text}"
    data, error = _assert_response_and_unwrap_envelope(response)
    assert data
    assert not error
    services_list = data
    assert len(services_list) == len(user_ids) * len(project_ids) * NUM_SERVICES

    # cleanup
    for service in created_services:
        resp = await client.delete(
            f"/{api_version_prefix}/running_interactive_services/{service['service_uuid']}",
            params={"save_state": False},
        )
        assert resp.status_code == status.HTTP_204_NO_CONTENT, resp.text
