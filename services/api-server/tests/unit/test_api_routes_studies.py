# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterator

import httpx
import pytest
import respx
from faker import Faker
from fastapi import FastAPI, status
from respx import MockRouter
from simcore_service_api_server.core.settings import ApplicationSettings


@pytest.fixture(scope="session")
def webserver_service_openapi_specs(
    osparc_simcore_services_dir: Path,
) -> dict[str, Any]:

    openapi_path = (
        osparc_simcore_services_dir
        / "web/server/src/simcore_service_webserver/api/v0/openapi.yaml"
    )
    openapi_specs = json.loads(openapi_path.read_text())
    return openapi_specs


@pytest.fixture
def fake_study_ports(faker: Faker) -> list[dict[str, Any]]:
    return [
        # input
        {
            "key": faker.uuid4(),
            "kind": "input",
            "content_schema": {
                "title": "X",
                "type": "integer",
                "x_unit": "second",
                "minimum": 0,
                "maximum": 5,
            },
        },
        # output
        {
            "key": faker.uuid4(),
            "kind": "ouput",
            "content_schema": {
                "title": "Y",
                "type": "integer",
            },
        },
    ]


@pytest.fixture
def fake_study_input(fake_study_ports: dict[str, Any]) -> dict[str, Any]:
    input_port = next(p for p in fake_study_ports if p["kind"] == "input")
    return {
        "key": input_port["key"],
        "value": 2,
        "label": input_port["content_schema"]["title"],
    }


@pytest.fixture
def fake_study_output(faker: Faker, fake_study_ports: dict[str, Any]) -> dict[str, Any]:
    output_port = next(p for p in fake_study_ports if p["kind"] == "output")
    return {
        "key": output_port["key"],
        "value": 42,
        "label": output_port["content_schema"]["title"],
    }


@pytest.fixture
def mocked_webserver_service_api(
    app: FastAPI,
    webserver_service_openapi_specs: dict[str, Any],
    fake_study_ports: list[dict[str, Any]],
    fake_study_input: dict[str, Any],
    fake_study_output: dict[str, Any],
    faker: Faker,
) -> Iterator[MockRouter]:
    """
    Mocks web/server http API
    """
    settings: ApplicationSettings = app.state.settings
    assert settings.API_SERVER_WEBSERVER

    # TODO: add more examples in openapi!
    openapi = deepcopy(webserver_service_openapi_specs)
    oas_paths = openapi["paths"]

    # DATA ---
    study_ports = fake_study_ports
    study_inputs = {fake_study_input["key"]: fake_study_input}
    study_outputs = {fake_study_output["key"]: fake_study_output}

    def _update_project_inputs(request: httpx.Request):
        changes = json.loads(request.content.decode(request.headers.encoding))
        study_inputs.update(*changes)
        return httpx.Response(status.HTTP_200_OK, json={"data": study_inputs})

    # ENTRYPOINTS ---------
    # pylint: disable=not-context-manager
    with respx.mock(
        base_url=settings.API_SERVER_WEBSERVER.base_url,
        assert_all_called=False,
        assert_all_mocked=True,
    ) as respx_mock:

        # Mocks /health
        assert oas_paths["/health"]
        respx_mock.get("/v0/health").respond(
            200,
            json={
                "data": {
                    "name": "simcore-director-service",
                    "status": "SERVICE_RUNNING",
                    "api_version": "0.1.0-dev+NJuzzD9S",
                    "version": "0.1.0-dev+N127Mfv9H",
                }
            },
        )

        # Mocks /projects/{*}/ports
        assert oas_paths["/projects/{project_id}/ports"]
        assert "get" in oas_paths["/projects/{project_id}/ports"].keys()
        respx_mock.get(
            path__regex=r"/v0/projects/(?P<project_id>[\w-]+)/ports",
            name="get_project_ports",
        ).respond(
            200,
            json={"data": study_ports},
        )

        # Mocks /projects/{*}/inputs
        assert oas_paths["/projects/{project_id}/inputs"]
        assert "get" in oas_paths["/projects/{project_id}/inputs"].keys()
        respx_mock.get(
            path__regex=r"/v0/projects/(?P<project_id>[\w-]+)/inputs",
            name="get_project_inputs",
        ).respond(
            200,
            # Envelope[dict[uuid.UUID, ProjectPortGet]
            json={
                "data": study_inputs,
                "error": None,
            },
        )

        assert "patch" in oas_paths["/projects/{project_id}/inputs"].keys()
        respx_mock.patch(
            path__regex=r"/v0/projects/(?P<project_id>[\w-]+)/inputs",
            name="update_project_inputs",
        ).respond(
            200,
            side_effect=_update_project_inputs,
        )

        # Mocks /projects/{*}/outputs
        assert oas_paths["/projects/{project_id}/outputs"]
        assert "get" in oas_paths["/projects/{project_id}/outputs"].keys()
        respx_mock.get(
            path__regex=r"/v0/projects/(?P<project_id>[\w-]+)/outputs",
            name="get_project_outputs",
        ).respond(
            200,
            # Envelope[dict[uuid.UUID, ProjectPortGet]
            json={
                "data": study_outputs,
                "error": None,
            },
        )

        yield respx_mock


async def test_study_io_ports_workflow(
    client: httpx.AsyncClient,
    mocked_webserver_service_api: MockRouter,
    faker: Faker,
    fake_study_ports: list[dict[str, Any]],
    fake_study_input: dict[str, Any],
    fake_study_output: dict[str, Any],
):
    study_id = faker.uuid4()
    input_port_key = fake_study_input["key"]

    # list studies
    resp = await client.get("/v0/studies")
    assert resp.status_code == status.HTTP_200_OK

    # list_study_ports
    resp = await client.get(f"/v0/study/{study_id}/ports")
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json() == fake_study_ports

    # get_study_inputs
    resp = await client.get(f"/v0/study/{study_id}/inputs")
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json() == {fake_study_input["key"]: fake_study_input}

    # update_study_inputs
    resp = await client.patch(
        f"/v0/study/{study_id}/inputs", [{"key": input_port_key, "value": 2}]
    )
    assert resp.status_code == status.HTTP_200_OK

    # list_study_inputs
    resp = await client.get(f"/v0/study/{study_id}/inputs")
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json() == {
        input_port_key: {
            "key": input_port_key,
            "value": 2,  # <---- updated
            "label": "X",
        },
    }

    # get_study_outputs
    resp = await client.get(f"/v0/study/{study_id}/outputs")
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json() == {fake_study_output["key"]: fake_study_output}
