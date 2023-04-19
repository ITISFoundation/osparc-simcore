# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import json
from typing import Any, Callable

import pytest
from models_library.generics import Envelope
from models_library.utils.database_models_factory import (
    create_pydantic_model_from_sa_table,
)
from models_library.utils.pydantic_models_factory import copy_model
from pydantic import validator
from pytest_simcore.simcore_webserver_projects_rest_api import NEW_PROJECT
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver._resources import resources
from simcore_service_webserver.projects._project_models_rest import ProjectSchema
from simcore_service_webserver.projects.projects_db import projects as projects_table

#


@pytest.fixture
def project_jsonschema():
    with resources.stream(f"api/{API_VTAG}/schemas/project-v0.0.1-pydantic.json") as fh:
        return json.load(fh)


#
#
# These tests uses requests/reponse calls (pytest_simcore.simcore_webserver_projects_rest_api)
# captured from the front-end (i.e. copy&pasted from browser devtols) and emulate workflows
# that parse data at different interfaces and directions.
#
# TODO: see https://github.com/ITISFoundation/osparc-simcore/issues/2725
# TODO: ANE's input: group namespace for all model variantes
#  of a resource model incluing default definitions
#
# e.g.
#   ProjectCRUDModels = ModelsCRUDGroup[ProjectSchema]
#   ProjectCRUDModels.Create(include={
#             "name",
#             "description",
#             "prjOwner",
#             "thumbnail",
#             "workbench",
#         },)
#   ProjectCRUDModels.Update()
#   ...
#
#
# TODO: ANE's input: add trace of reference class (e.g. __copy_model_ref__)
#


@pytest.mark.skip(reason="DEV")
def test_models_when_creating_new_empty_project():
    class _ProjectCreate(
        copy_model(
            ProjectSchema,
            name="ProjectCreateBase",
            include={
                "name",
                "description",
                "prjOwner",
                "thumbnail",
                "workbench",
            },
            # defaults to Extra.ignore
        )
    ):
        @validator("thumbnail", pre=True)
        @classmethod
        def default_thumbnail(cls, v):
            if not v:
                return None
            return v

    # use _ProjectCreate to parse & validate request payload in POST /projects
    project_req_payload = _ProjectCreate.parse_obj(NEW_PROJECT.request_payload)

    assert project_req_payload.dict(exclude_unset=True) == {
        "name": "New Study",
        "description": "",
        "thumbnail": None,
        "workbench": {},
    }

    # Model to insert
    # - exclude all fields that have to be defined on the server side:
    #   - id: primary key and handled by server
    #   - creation_date, last_change_date: defined on server sdie

    #
    #
    #
    _ProjectInsert = create_pydantic_model_from_sa_table(
        table=projects_table,
    )

    # we insert a row in the db and fetch it back (w/ a primary-key, ...)
    _ProjectFetch = copy_model(ProjectSchema, name="ProjectFetch")

    project_new = _ProjectFetch()

    # compose other parts into response
    _ProjectGet = copy_model(
        ProjectSchema,
        name="ProjectGet",
    )

    project_new = _ProjectGet.parse_obj(project_new.dict())

    project_resp_body = Envelope.parse_data(project_new)
    assert project_resp_body.dict() == NEW_PROJECT.response_body


@pytest.mark.skip(reason="DEV")
def test_generated_model_in_sync_with_json_schema_specs(
    diff_json_schemas: Callable, project_jsonschema: dict[str, Any]
):
    def assert_equivalent_schemas(lhs: dict, rhs: dict):

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
    assert_equivalent_schemas(project_jsonschema, ProjectSchema.schema())

    # run other way direction:  generated one encompass original schema
    assert_equivalent_schemas(ProjectSchema.schema(), project_jsonschema)
