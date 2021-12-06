# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

#
# These tests were build following requests/reponse calls from the front-end
# i.e. it captures models created by the front-end and response models by the backend
#


from typing import Any, Dict

from pydantic import create_model
from pytest_simcore.simcore_webserver_projects_rest_api import (
    CLOSE_PROJECT,
    GET_PROJECT,
    LIST_PROJECTS,
    NEW_PROJECT,
    OPEN_PROJECT,
    REPLACE_PROJECT,
    REPLACE_PROJECT_ON_MODIFIED,
    RUN_PROJECT,
)
from simcore_service_webserver.projects._project_models_rest import SimcoreProject

# TODO: how could we implement all the model variants provided SimcoreProject as base???
#
# https://github.com/samuelcolvin/pydantic/issues/830#issuecomment-534141136
#
# 1. Use create_model to create your models "dynamically" (even if you actually do it un-dynamically)
# 2. Make the extra fields optional so they can be ignored.
#
# but there is a new __exclude_fields__ feature coming with https://github.com/samuelcolvin/pydantic/pull/2231


CreateProject = create_model(
    "CreateProject",
    **{
        name: (
            field.type_,
            field.default or field.default_factory or (... if field.required else None),
        )
        for name, field in SimcoreProject.__fields__.items()
        if name
        in {
            "name",
            "description",
            "thumbnail",
            "prj_owner",
            "access_rights",
        }
    }
)


# class ProjectInNew(BaseModel):
#    pass

# name:
# description:
# thumbnail:
# prj_owner:
# access_rights:


#    name: SimcoreProject.__fields__[]


class ProjectAsBody(SimcoreProject):
    pass


def test_models_when_creating_new_empty_project():

    project_in_new = ProjectAsBody.parse_obj(NEW_PROJECT.request_payload)
    assert NEW_PROJECT.response_body
    project_as_body = ProjectAsBody.parse_obj(NEW_PROJECT.response_body["data"])


def test_models_when_replacing_an_opened_project():

    project_in_replace = ProjectAsBody.parse_obj(REPLACE_PROJECT.request_payload)
    assert REPLACE_PROJECT.response_body
    project_as_body = ProjectAsBody.parse_obj(REPLACE_PROJECT.response_body["data"])


def test_models_when_saving_after_project_change():

    project_in_replace = ProjectAsBody.parse_obj(
        REPLACE_PROJECT_ON_MODIFIED.request_payload
    )
    assert REPLACE_PROJECT_ON_MODIFIED.response_body
    project_as_body = ProjectAsBody.parse_obj(
        REPLACE_PROJECT_ON_MODIFIED.response_body["data"]
    )
