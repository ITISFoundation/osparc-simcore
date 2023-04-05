import pytest
from models_library.rest_pagination import Page
from pydantic import parse_obj_as
from pytest_simcore.simcore_webserver_projects_rest_api import (
    LIST_PROJECTS,
    SESSION_WORKFLOW,
    HttpApiCallCapture,
)
from simcore_service_webserver.projects.oas_schemas import (
    ProjectCreate,
    ProjectListItem,
)


@pytest.mark.parametrize(
    "api_call",
    (
        capture
        for capture in SESSION_WORKFLOW
        if capture.method == "POST" and capture.path == "/v0/projects"
    ),
    ids=lambda c: c.name,
)
def test_project_create_model(api_call: HttpApiCallCapture):

    model = ProjectCreate.parse_obj(api_call.request_payload)

    assert model


@pytest.mark.parametrize(
    "api_call",
    (LIST_PROJECTS,),
    ids=lambda c: c.name,
)
def test_list_project_model(api_call: HttpApiCallCapture):

    model = parse_obj_as(Page[ProjectListItem], api_call.request_payload)

    assert model
