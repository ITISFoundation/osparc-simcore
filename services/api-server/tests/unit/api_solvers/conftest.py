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
import yaml
from faker import Faker
from fastapi import FastAPI, status
from models_library.projects import Project
from models_library.utils.fastapi_encoders import jsonable_encoder
from pytest_simcore.helpers import faker_catalog
from respx import MockRouter
from simcore_service_api_server.core.settings import ApplicationSettings


@pytest.fixture
def catalog_service_openapi_specs(osparc_simcore_services_dir: Path) -> dict[str, Any]:
    openapi_path = osparc_simcore_services_dir / "catalog" / "openapi.json"
    openapi_specs = json.loads(openapi_path.read_text())
    return openapi_specs


@pytest.fixture
def directorv2_service_openapi_specs(
    osparc_simcore_services_dir: Path,
) -> dict[str, Any]:
    return json.loads(
        (osparc_simcore_services_dir / "director-v2" / "openapi.json").read_text()
    )


@pytest.fixture
def webserver_service_openapi_specs(
    osparc_simcore_services_dir: Path,
) -> dict[str, Any]:
    return yaml.safe_load(
        (
            osparc_simcore_services_dir
            / "web/server/src/simcore_service_webserver/api/v0/openapi.yaml"
        ).read_text()
    )


@pytest.fixture
def mocked_webserver_service_api(
    app: FastAPI, webserver_service_openapi_specs: dict[str, Any], faker: Faker
) -> Iterator[MockRouter]:
    settings: ApplicationSettings = app.state.settings
    assert settings.API_SERVER_WEBSERVER

    openapi = deepcopy(webserver_service_openapi_specs)

    # pylint: disable=not-context-manager
    with respx.mock(
        base_url=settings.API_SERVER_WEBSERVER.base_url,
        assert_all_called=False,
        assert_all_mocked=True,
    ) as respx_mock:

        # include /v0
        assert settings.API_SERVER_WEBSERVER.base_url.endswith("/v0")

        # healthcheck_readiness_probe, healthcheck_liveness_probe
        response_body = {
            "data": openapi["paths"]["/"]["get"]["responses"]["200"]["content"][
                "application/json"
            ]["schema"]["properties"]["data"]["example"]
        }

        respx_mock.get(path="/v0/", name="healthcheck_readiness_probe").respond(
            status.HTTP_200_OK, json=response_body
        )
        respx_mock.get(path="/v0/health", name="healthcheck_liveness_probe").respond(
            status.HTTP_200_OK, json=response_body
        )

        class _SideEffects:
            def __init__(self):
                # cached
                self._projects: dict[str, Project] = {}

            @staticmethod
            def get_body_as_json(request):
                return json.load(request.stream)

            def create_project(self, request: httpx.Request):
                task_id = faker.uuid4()

                project_create = self.get_body_as_json(request)
                self._projects[task_id] = Project(**project_create)

                return httpx.Response(
                    status.HTTP_202_ACCEPTED,
                    json={
                        "data": {
                            "task_id": task_id,
                            "status_href": f"{settings.API_SERVER_WEBSERVER.base_url}/tasks/{task_id}",
                            "result_href": f"{settings.API_SERVER_WEBSERVER.base_url}/tasks/{task_id}/result",
                        }
                    },
                )

            def get_result(self, request: httpx.Request, *, task_id: str):
                # TODO: replace with ProjectGet
                project_get = jsonable_encoder(
                    self._projects[task_id].dict(by_alias=True)
                )
                return httpx.Response(
                    status.HTTP_200_OK,
                    json={"data": project_get},
                )

        fake_workflow = _SideEffects()

        # http://webserver:8080/v0/projects?hidden=true
        respx_mock.post(
            path__regex="/projects$",
            name="create_projects",
        ).mock(side_effect=fake_workflow.create_project)

        respx_mock.get(
            path__regex=r"/tasks/(?P<task_id>[\w-]+)/result$",
            name="get_task_result",
        ).mock(side_effect=fake_workflow.get_result)

        respx_mock.get(
            path__regex=r"/tasks/(?P<task_id>[\w/%]+)",
            name="get_task_status",
        ).respond(
            status.HTTP_200_OK,
            json={
                "data": {
                    "task_progress": {"message": "fake job done", "percent": 1},
                    "done": True,
                    "started": "2018-07-01T11:13:43Z",
                }
            },
        )

        yield respx_mock


@pytest.fixture
def mocked_catalog_service_api(
    app: FastAPI, catalog_service_openapi_specs: dict[str, Any]
) -> Iterator[MockRouter]:
    settings: ApplicationSettings = app.state.settings
    assert settings.API_SERVER_CATALOG

    openapi = deepcopy(catalog_service_openapi_specs)
    schemas = openapi["components"]["schemas"]

    # pylint: disable=not-context-manager
    with respx.mock(
        base_url=settings.API_SERVER_CATALOG.base_url,
        assert_all_called=False,
        assert_all_mocked=True,
    ) as respx_mock:

        respx_mock.get("/v0/meta").respond(200, json=schemas["Meta"]["example"])

        # ----
        respx_mock.get(
            "/v0/services?user_id=1&details=false", name="list_services"
        ).respond(
            200,
            json=[
                # one solver
                faker_catalog.create_service_out(
                    key="simcore/services/comp/Foo", name="Foo"
                ),
                # two version of the same solver
                faker_catalog.create_service_out(version="0.0.1"),
                faker_catalog.create_service_out(version="1.0.1"),
                # not a solver
                faker_catalog.create_service_out(type="dynamic"),
            ],
        )

        # -----
        # NOTE: we could use https://python-jsonschema.readthedocs.io/en/stable/
        #

        respx_mock.get(
            # NOTE: regex does not work even if tested https://regex101.com/r/drVAGr/1
            # path__regex=r"/v0/services/(?P<service_key>[\w/%]+)/(?P<service_version>[\d\.]+)/ports\?user_id=(?P<user_id>\d+)",
            path__startswith="/v0/services/simcore%2Fservices%2Fcomp%2Fitis%2Fsleeper/2.1.4/ports",
            name="list_service_ports",
        ).respond(
            200,
            json=[
                schemas["ServicePortGet"]["example"],
            ],
        )

        yield respx_mock
