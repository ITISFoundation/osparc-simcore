import pytest
from models_library.generics import Envelope
from models_library.rest_pagination import Page
from pydantic import parse_obj_as
from pytest_simcore.simcore_webserver_projects_rest_api import (
    GET_PROJECT,
    LIST_PROJECTS,
    NEW_PROJECT,
    REPLACE_PROJECT,
    REPLACE_PROJECT_ON_MODIFIED,
    HttpApiCallCapture,
)
from simcore_service_webserver.projects._rest_schemas import (
    ProjectCreate,
    ProjectGet,
    ProjectListItem,
    ProjectReplace,
)


@pytest.mark.parametrize(
    "api_call",
    (NEW_PROJECT,),
    ids=lambda c: c.name,
)
def test_create_project_schemas(api_call: HttpApiCallCapture):

    request_payload = ProjectCreate.parse_obj(api_call.request_payload)
    assert request_payload

    response_body = parse_obj_as(Envelope[ProjectGet], api_call.response_body)
    assert response_body


@pytest.mark.parametrize(
    "api_call",
    (LIST_PROJECTS,),
    ids=lambda c: c.name,
)
def test_list_project_schemas(api_call: HttpApiCallCapture):

    request_payload = parse_obj_as(Page[ProjectListItem], api_call.request_payload)
    assert request_payload


@pytest.mark.testit
@pytest.mark.parametrize(
    "api_call",
    (GET_PROJECT,),
    ids=lambda c: c.name,
)
def test_get_project_schemas(api_call: HttpApiCallCapture):

    response_body = parse_obj_as(Envelope[ProjectGet], api_call.response_body)
    assert response_body


@pytest.mark.parametrize(
    "api_call",
    (REPLACE_PROJECT, REPLACE_PROJECT_ON_MODIFIED),
    ids=lambda c: c.name,
)
def test_replace_project_schemas(api_call: HttpApiCallCapture):

    request_payload = parse_obj_as(ProjectReplace, api_call.request_payload)
    assert request_payload

    response_body = parse_obj_as(Envelope[ProjectGet], api_call.response_body)
    assert response_body
