""" Helper script to automatically generate OAS

This OAS are the source of truth
"""

# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from enum import Enum

from _common import (
    CURRENT_DIR,
    assert_handler_signature_against_model,
    create_openapi_specs,
)
from fastapi import FastAPI, Query, status
from models_library.api_schemas_webserver.projects import (
    ProjectCopyOverride,
    ProjectCreateNew,
    ProjectGet,
    ProjectListItem,
    ProjectReplace,
    ProjectUpdate,
    TaskGet,
)
from models_library.generics import Envelope
from models_library.projects import ProjectID
from models_library.rest_pagination import (
    DEFAULT_NUMBER_OF_ITEMS_PER_PAGE,
    MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE,
    Page,
)
from pydantic import NonNegativeInt
from servicelib.aiohttp.long_running_tasks.server import TaskGet
from simcore_service_webserver.projects._handlers_crud import (
    ProjectPathParams,
    ProjectTypeAPI,
    _ProjectActiveParams,
    _ProjectCreateParams,
    _ProjectListParams,
)

app = FastAPI(redoc_url=None)

TAGS: list[str | Enum] = [
    "project",
]


#
# API entrypoints
#


@app.post(
    "/projects",
    response_model=Envelope[TaskGet],
    summary="Creates a new project or copies an existing one",
    status_code=status.HTTP_201_CREATED,
    tags=TAGS,
    operation_id="create_project",
)
async def create_project(
    create: ProjectCreateNew | ProjectCopyOverride,
    from_study: ProjectID
    | None = Query(
        None,
        description="Option to create a project from existing template or study: from_study={study_uuid}",
    ),
    as_template: bool = Query(
        False,
        description="Option to create a template from existing project: as_template=true",
    ),
    copy_data: bool = Query(
        True,
        description="Option to copy data when creating from an existing template or as a template, defaults to True",
    ),
    hidden: bool = Query(
        False,
        description="Enables/disables hidden flag. Hidden projects are by default unlisted",
    ),
):
    ...


assert_handler_signature_against_model(create_project, _ProjectCreateParams)


@app.get(
    "/projects",
    response_model=Page[ProjectListItem],
    tags=TAGS,
    operation_id="list_projects",
)
async def list_projects(
    limit: int = Query(
        default=DEFAULT_NUMBER_OF_ITEMS_PER_PAGE,
        description="maximum number of items to return (pagination)",
        ge=1,
        lt=MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE,
    ),
    offset: NonNegativeInt = Query(
        default=0, description="index to the first item to return (pagination)"
    ),
    project_type: ProjectTypeAPI = Query(default=ProjectTypeAPI.all, alias="type"),
    show_hidden: bool = Query(
        default=False, description="includes projects marked as hidden in the listing"
    ),
    order_by: str
    | None = Query(
        default=None,
        description="Comma separated list of fields for ordering. The default sorting order is ascending. To specify descending order for a field, users append a 'desc' suffix",
        example="foo desc, bar",
    ),
    filters: str
    | None = Query(
        default=None,
        description="Filters to process on the projects list, encoded as JSON",
        example='{"tags": [1, 5], "classifiers": ["foo", "bar"]}',
    ),
    search: str = Query(
        default=None,
        description="Multi column full text search",
        max_length=25,
        example="My project",
    ),
):
    ...


# NOTE: filters and order_by are not yet implemented
assert_handler_signature_against_model(list_projects, _ProjectListParams)


@app.get(
    "/projects/active",
    response_model=Envelope[ProjectGet],
    tags=TAGS,
    operation_id="get_active_project",
)
async def get_active_project(client_session_id: str):
    ...


assert_handler_signature_against_model(get_active_project, _ProjectActiveParams)


@app.get(
    "/projects/{project_id}",
    response_model=Envelope[ProjectGet],
    tags=TAGS,
    operation_id="get_project",
)
async def get_project(project_id: ProjectID):
    ...


assert_handler_signature_against_model(get_project, ProjectPathParams)


@app.put(
    "/projects/{project_id}",
    response_model=Envelope[ProjectGet],
    tags=TAGS,
    operation_id="replace_project",
)
async def replace_project(project_id: ProjectID, replace: ProjectReplace):
    """Replaces (i.e. full update) a project resource"""


assert_handler_signature_against_model(replace_project, ProjectPathParams)


@app.patch(
    "/projects/{project_id}",
    response_model=Envelope[ProjectGet],
    tags=TAGS,
    operation_id="update_project",
)
async def update_project(project_id: ProjectID, update: ProjectUpdate):
    """Partial update of a project resource"""


assert_handler_signature_against_model(update_project, ProjectPathParams)


@app.delete(
    "/projects/{project_id}",
    tags=TAGS,
    operation_id="delete_project",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_project(project_id: ProjectID):
    ...


assert_handler_signature_against_model(delete_project, ProjectPathParams)


if __name__ == "__main__":

    create_openapi_specs(app, CURRENT_DIR.parent / "openapi-projects-crud.yaml")
