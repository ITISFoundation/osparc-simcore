# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import json
from typing import Any, Callable, Dict

import pytest
from models_library.generics import Envelope
from models_library.utils.pydantic_models_factory import copy_model
from pytest_simcore.simcore_webserver_projects_rest_api import NEW_PROJECT
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver.projects._project_models_rest import SimcoreProject
from simcore_service_webserver.resources import resources

## FIXTURES --------------------------------------------------


@pytest.fixture
def project_jsonschema():
    with resources.stream(f"api/{API_VTAG}/schemas/project-v0.0.1.json") as fh:
        return json.load(fh)


## TESTS ----------------------------------------------------
#
# These tests uses requests/reponse calls (pytest_simcore.simcore_webserver_projects_rest_api)
# captured from the front-end (i.e. copy&pasted from browser devtols) and emulate workflows
# that parse data at different interfaces and directions.
#
#


def test_models_when_creating_new_empty_project():

    _ProjectCreate = copy_model(
        SimcoreProject,
        name="ProjectCreate",
        exclude_optionals=True,
    )

    # use _ProjectCreate to parse request payload in POST /projects
    project_req_payload = _ProjectCreate.parse_obj(NEW_PROJECT.request_payload)

    # we insert a row in the db and fetch it back (w/ a primary-key, ...)
    _ProjectFetch = copy_model(SimcoreProject, name="ProjectFetch")

    project_new = _ProjectFetch()

    # compose other parts into response
    _ProjectGet = copy_model(
        SimcoreProject,
        name="ProjectGet",
    )

    project_new = _ProjectGet.parse_obj(project_new.dict())

    project_resp_body = Envelope.parse_data(project_new)
    assert project_resp_body.dict() == NEW_PROJECT.response_body


def test_generated_model_in_sync_with_json_schema_specs(
    diff_json_schemas: Callable, project_jsonschema: Dict[str, Any]
):
    def assert_equivalent_schemas(lhs: Dict, rhs: Dict):

        process_completion = diff_json_schemas(lhs, rhs)

        assert (
            process_completion.returncode == 0
        ), f"Exit code {process_completion.returncode}\n{process_completion.stdout.decode('utf-8')}"

        # https://www.npmjs.com/package/json-schema-diff returns true (at least in WSL whatever the result)
        # ```false``` is returned at the end of the stdout
        assert "No differences found" in process_completion.stdout.decode(
            "utf-8"
        ), process_completion.stdout.decode("utf-8")

    # run one direction original schema encompass generated one
    assert_equivalent_schemas(project_jsonschema, SimcoreProject.schema())

    # run other way direction:  generated one encompass original schema
    assert_equivalent_schemas(SimcoreProject.schema(), project_jsonschema)
