# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import json
from copy import deepcopy
from typing import Any

import httpx
import pytest
from faker import Faker
from fastapi import FastAPI, status
from models_library.api_schemas_webserver.projects import ProjectGet
from models_library.utils.fastapi_encoders import jsonable_encoder
from pytest_simcore.helpers import faker_catalog
from respx import MockRouter
from simcore_service_api_server.core.settings import ApplicationSettings


@pytest.fixture
def solver_key() -> str:
    return "simcore/services/comp/itis/sleeper"


@pytest.fixture
def solver_version() -> str:
    return "2.0.0"


@pytest.fixture
def mocked_webserver_service_api(
    app: FastAPI, mocked_webserver_service_api_base: MockRouter, faker: Faker
) -> MockRouter:
    settings: ApplicationSettings = app.state.settings
    assert settings.API_SERVER_WEBSERVER

    class _SideEffects:
        def __init__(self):
            # cached
            self._projects: dict[str, ProjectGet] = {}

        @staticmethod
        def get_body_as_json(request):
            return json.load(request)

        def create_project(self, request: httpx.Request):
            task_id = faker.uuid4()

            project_create = self.get_body_as_json(request)
            self._projects[task_id] = ProjectGet.parse_obj(
                {
                    "creationDate": "2018-07-01T11:13:43Z",
                    "lastChangeDate": "2018-07-01T11:13:43Z",
                    "prjOwner": "owner@email.com",
                    **project_create,
                }
            )

            return httpx.Response(
                status.HTTP_202_ACCEPTED,
                json={
                    "data": {
                        "task_id": task_id,
                        "status_href": f"{settings.API_SERVER_WEBSERVER.api_base_url}/tasks/{task_id}",
                        "result_href": f"{settings.API_SERVER_WEBSERVER.api_base_url}/tasks/{task_id}/result",
                    }
                },
            )

        def get_result(self, request: httpx.Request, *, task_id: str):
            # TODO: replace with ProjectGet
            project_get = jsonable_encoder(self._projects[task_id].dict(by_alias=True))
            return httpx.Response(
                status.HTTP_200_OK,
                json={"data": project_get},
            )

    fake_workflow = _SideEffects()

    # http://webserver:8080/v0/projects?hidden=true
    mocked_webserver_service_api_base.post(
        path__regex="/projects$",
        name="create_projects",
    ).mock(side_effect=fake_workflow.create_project)

    mocked_webserver_service_api_base.get(
        path__regex=r"/tasks/(?P<task_id>[\w-]+)/result$",
        name="get_task_result",
    ).mock(side_effect=fake_workflow.get_result)

    mocked_webserver_service_api_base.get(
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

    return mocked_webserver_service_api_base


@pytest.fixture
def mocked_catalog_service_api(
    app: FastAPI,
    mocked_catalog_service_api_base: MockRouter,
    catalog_service_openapi_specs: dict[str, Any],
) -> MockRouter:
    respx_mock = mocked_catalog_service_api_base
    openapi = deepcopy(catalog_service_openapi_specs)
    schemas = openapi["components"]["schemas"]

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

    return respx_mock
