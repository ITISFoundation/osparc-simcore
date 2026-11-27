# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from typing import Any

import pytest
from models_library.api_schemas_webserver.projects import (
    ProjectCopyOverride,
    ProjectCreateNew,
    ProjectGet,
    ProjectListItem,
    ProjectReplace,
    TaskProjectGet,
)
from models_library.generics import Envelope
from models_library.rest_pagination import Page
from pydantic import TypeAdapter, ValidationError
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
    [NEW_PROJECT, CREATE_FROM_SERVICE, CREATE_FROM_TEMPLATE],
    ids=lambda c: c.name,
)
def test_create_project_schemas(api_call: HttpApiCallCapture):
    request_payload = ProjectCreateNew.model_validate(api_call.request_payload)
    assert request_payload

    response_body = TypeAdapter(Envelope[ProjectGet] | Envelope[TaskProjectGet]).validate_python(api_call.response_body)
    assert response_body


@pytest.mark.parametrize(
    "tags,expected",
    [(None, {}), ([], {"tags": []}), ([3, 5], {"tags": [3, 5]})],
    ids=["omitted", "empty", "selected"],
)
def test_project_copy_override_preserves_tag_presence(tags: list[int] | None, expected: dict):
    payload: dict[str, Any] = {"name": "Copy", "prjOwner": "user@example.com"}
    if tags is not None:
        payload["tags"] = tags

    override = ProjectCopyOverride.model_validate(payload).to_domain_model()
    assert {key: override[key] for key in override if key == "tags"} == expected


@pytest.mark.parametrize(
    "tags", [None, "invalid", ["invalid"], {"id": 1}], ids=["null", "string", "bad-item", "object"]
)
def test_project_copy_override_rejects_invalid_tags(tags: Any):
    with pytest.raises(ValidationError):
        ProjectCopyOverride.model_validate({"name": "Copy", "prjOwner": "user@example.com", "tags": tags})


@pytest.mark.parametrize(
    "api_call",
    [LIST_PROJECTS],
    ids=lambda c: c.name,
)
def test_list_project_schemas(api_call: HttpApiCallCapture):
    assert api_call.request_payload is None

    response_body = TypeAdapter(Page[ProjectListItem]).validate_python(api_call.response_body)
    assert response_body


@pytest.mark.parametrize(
    "api_call",
    [GET_PROJECT, CREATE_FROM_TEMPLATE__TASK_RESULT],
    ids=lambda c: c.name,
)
def test_get_project_schemas(api_call: HttpApiCallCapture):
    # NOTE: that response_body here is the exported values
    # and therefore ProjectGet has to be implemented in such a way that
    # can also parse exported values! (e.g. Json does not allow that, or occasionally exclude_none)
    response_body = TypeAdapter(Envelope[ProjectGet]).validate_python(api_call.response_body)
    assert response_body


@pytest.mark.parametrize(
    "api_call",
    [REPLACE_PROJECT, REPLACE_PROJECT_ON_MODIFIED],
    ids=lambda c: c.name,
)
def test_replace_project_schemas(api_call: HttpApiCallCapture):
    request_payload = TypeAdapter(ProjectReplace).validate_python(api_call.request_payload)
    assert request_payload

    response_body = TypeAdapter(Envelope[ProjectGet]).validate_python(api_call.response_body)
    assert response_body
