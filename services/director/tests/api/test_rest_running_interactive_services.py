# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import uuid

import httpx
import pytest
from aioresponses.core import CallbackResult, aioresponses
from fastapi import status


def _assert_response_and_unwrap_envelope(got: httpx.Response):
    assert got.encoding == "application/json"

    body = got.json()
    assert isinstance(body, dict)
    assert "data" in body or "error" in body
    return body.get("data"), body.get("error")


@pytest.mark.skip(
    reason="docker_swarm fixture is a session fixture making it bad running together with other tests that require a swarm"
)
async def test_running_services_post_and_delete_no_swarm(
    configure_swarm_stack_name,
    client: httpx.AsyncClient,
    push_services,
    user_id,
    project_id,
    api_version_prefix,
):
    params = {
        "user_id": "None",
        "project_id": "None",
        "service_uuid": "sdlfkj4",
        "service_key": "simcore/services/comp/some-key",
    }
    resp = await client.post(
        f"/{api_version_prefix}/running_interactive_services", params=params
    )
    data = resp.json()
    assert resp.status_code == 500, data


@pytest.mark.parametrize(
    "save_state, expected_save_state_call", [(True, True), (False, False), (None, True)]
)
async def test_running_services_post_and_delete(
    configure_swarm_stack_name,
    client: httpx.AsyncClient,
    push_services,
    docker_swarm,
    user_id,
    project_id,
    api_version_prefix,
    save_state: bool | None,
    expected_save_state_call: bool,
    mocker,
):
    params = {}
    resp = await client.post(
        f"/{api_version_prefix}/running_interactive_services", params=params
    )
    assert resp.status_code == status.HTTP_400_BAD_REQUEST

    params = {
        "user_id": "None",
        "project_id": "None",
        "service_uuid": "sdlfkj4",
        "service_key": "None",
        "service_tag": "None",  # optional
        "service_basepath": "None",  # optional
    }
    resp = await client.post(
        f"/{api_version_prefix}/running_interactive_services", params=params
    )
    data = resp.json()
    assert resp.status_code == status.HTTP_400_BAD_REQUEST, data

    params["service_key"] = "simcore/services/comp/somfunkyname-nhsd"
    params["service_tag"] = "1.2.3"
    resp = await client.post(
        f"/{api_version_prefix}/running_interactive_services", params=params
    )
    data = resp.json()
    assert resp.status_code == status.HTTP_404_NOT_FOUND, data

    created_services = await push_services(0, 2)
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
        resp = await client.post(
            f"/{api_version_prefix}/running_interactive_services", params=params
        )
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.encoding == "application/json"
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
        assert resp.encoding == "application/json", f"Got {text=}"
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

        mocked_save_state_cb = mocker.MagicMock(
            return_value=CallbackResult(status=200, payload={})
        )
        PASSTHROUGH_REQUESTS_PREFIXES = [
            "http://127.0.0.1",
            "http://localhost",
            "unix://",  # docker engine
            "ws://",  # websockets
        ]
        with aioresponses(passthrough=PASSTHROUGH_REQUESTS_PREFIXES) as mock:

            # POST /http://service_host:service_port service_basepath/state -------------------------------------------------
            mock.post(
                f"http://{service_host}:{service_port}{service_basepath}/state",
                status=200,
                callback=mocked_save_state_cb,
            )
            resp = await client.delete(
                f"/{api_version_prefix}/running_interactive_services/{params['service_uuid']}",
                params=query_params,
            )
            if expected_save_state_call:
                mocked_save_state_cb.assert_called_once()

        text = resp.text
        assert resp.status_code == status.HTTP_204_NO_CONTENT, text
        assert resp.encoding == "application/json"
        data = resp.json()
        assert data is None


async def test_running_interactive_services_list_get(
    client: httpx.AsyncClient, push_services, docker_swarm
):
    """Test case for running_interactive_services_list_get

    Returns a list of interactive services
    """
    user_ids = ["first_user_id", "second_user_id"]
    project_ids = ["first_project_id", "second_project_id", "third_project_id"]
    # prepare services
    NUM_SERVICES = 1
    created_services = await push_services(0, NUM_SERVICES)
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
                resp = await client.post(
                    "/v0/running_interactive_services", params=params
                )
                assert resp.status_code == 201
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
            data, error = _assert_response_and_unwrap_envelope(response.json())
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
            data, error = _assert_response_and_unwrap_envelope(response.json())
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
            data, error = _assert_response_and_unwrap_envelope(response.json())
            assert data
            assert not error
            services_list = data
            assert len(services_list) == len(user_ids) * NUM_SERVICES
