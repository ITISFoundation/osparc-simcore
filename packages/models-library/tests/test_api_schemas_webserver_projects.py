# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


import pytest
from models_library.api_schemas_webserver.projects import (
    ProjectCreateNew,
    ProjectGet,
    ProjectListItem,
    ProjectReplace,
    TaskProjectGet,
)
from models_library.generics import Envelope
from models_library.rest_pagination import Page
from pydantic import TypeAdapter
from pytest_simcore.simcore_webserver_projects_rest_api import (
    CREATE_FROM_SERVICE,
    CREATE_FROM_TEMPLATE,
    CREATE_FROM_TEMPLATE__TASK_RESULT,
    GET_PROJECT,
    LIST_PROJECTS,
    NEW_PROJECT,
    REPLACE_PROJECT,
    REPLACE_PROJECT_ON_MODIFIED,
    HttpApiCallCapture,
)


@pytest.mark.parametrize(
    "api_call",
    (NEW_PROJECT, CREATE_FROM_SERVICE, CREATE_FROM_TEMPLATE),
    ids=lambda c: c.name,
)
def test_create_project_schemas(api_call: HttpApiCallCapture):
    request_payload = ProjectCreateNew.model_validate(api_call.request_payload)
    assert request_payload

    response_body = TypeAdapter(
        Envelope[ProjectGet] | Envelope[TaskProjectGet]
    ).validate_python(api_call.response_body)
    assert response_body


@pytest.mark.parametrize(
    "api_call",
    (LIST_PROJECTS,),
    ids=lambda c: c.name,
)
def test_list_project_schemas(api_call: HttpApiCallCapture):
    assert api_call.request_payload is None

    response_body = TypeAdapter(Page[ProjectListItem]).validate_python(
        api_call.response_body
    )
    assert response_body


@pytest.mark.parametrize(
    "api_call",
    (GET_PROJECT, CREATE_FROM_TEMPLATE__TASK_RESULT),
    ids=lambda c: c.name,
)
def test_get_project_schemas(api_call: HttpApiCallCapture):
    # NOTE: that response_body here is the exported values
    # and therefore ProjectGet has to be implemented in such a way that
    # can also parse exported values! (e.g. Json does not allow that, or ocassionaly exclude_none)
    response_body = TypeAdapter(Envelope[ProjectGet]).validate_python(
        api_call.response_body
    )
    assert response_body


@pytest.mark.parametrize(
    "api_call",
    (REPLACE_PROJECT, REPLACE_PROJECT_ON_MODIFIED),
    ids=lambda c: c.name,
)
def test_replace_project_schemas(api_call: HttpApiCallCapture):
    request_payload = TypeAdapter(ProjectReplace).validate_python(
        api_call.request_payload
    )
    assert request_payload

    response_body = TypeAdapter(Envelope[ProjectGet]).validate_python(
        api_call.response_body
    )
    assert response_body
