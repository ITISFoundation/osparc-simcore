#
# Assists on the creation of project's OAS
#
# - Follows https://cloud.google.com/apis/design
# - check in https://editor.swagger.io/
#
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import json
import sys
from datetime import datetime
from math import ceil
from pathlib import Path
from types import FunctionType
from typing import Any, Callable, Dict, Generic, List, Optional, Type, TypeVar, Union
from uuid import UUID, uuid3

import simcore_service_webserver.projects.projects_handlers
import simcore_service_webserver.projects.projects_node_handlers
import simcore_service_webserver.snapshots_api_handlers
from fastapi import Depends, FastAPI
from fastapi import Path as PathParam
from fastapi import Query, Request, status
from fastapi.exceptions import HTTPException
from fastapi.routing import APIRoute, APIRouter
from models_library.services import PROPERTY_KEY_RE, Author
from pydantic import (
    BaseModel,
    Field,
    PositiveInt,
    StrictBool,
    StrictFloat,
    StrictInt,
    constr,
    validator,
)
from pydantic.generics import GenericModel
from pydantic.networks import HttpUrl
from servicelib.rest_pagination_utils import PageLinks, PageMetaInfoLimitOffset
from simcore_service_webserver.snapshots_models import SnapshotResource
from starlette.datastructures import URL

CURRENT_FILENAME_STEM = Path(sys.argv[0] if __name__ == "__main__" else __file__).stem
# FIXME: modify openapi output
#   - exclusiveMinimum should be boolean. SEE https://github.com/tiangolo/fastapi/issues/240
#   - examples is NOT allowed
#   - patternProperties NOT allowed


InputID = OutputID = constr(regex=PROPERTY_KEY_RE)

# WARNING: oder matters
BuiltinTypes = Union[StrictBool, StrictInt, StrictFloat, str]
DataSchema = Union[
    BuiltinTypes,
]  # any json schema?
DataLink = HttpUrl

DataSchema = Union[DataSchema, DataLink]

DataT = TypeVar("DataT")


class Error(BaseModel):
    code: int
    message: str


class Envelope(GenericModel, Generic[DataT]):
    data: Optional[DataT]
    error: Optional[Error]

    @validator("error", always=True)
    @classmethod
    def check_consistency(cls, v, values):
        if v is not None and values["data"] is not None:
            raise ValueError("must not provide both data and error")
        if v is None and values.get("data") is None:
            raise ValueError("must provide data or error")
        return v


ItemT = TypeVar("ItemT")

# FIXME: replace PageResponseLimitOffset
# FIXME: page envelope is inconstent since DataT != Page ??
class Page(GenericModel, Generic[ItemT]):
    meta: PageMetaInfoLimitOffset = Field(alias="_meta")
    links: PageLinks = Field(alias="_links")
    data: List[ItemT]

    @classmethod
    def create_obj(
        cls,
        data: List[Any],
        request_url: URL,
        total: int,
        limit: int,
        offset: int,
    ) -> Dict[str, Any]:
        last_page = ceil(total / limit) - 1
        return dict(
            _meta=PageMetaInfoLimitOffset(
                total=total, count=len(data), limit=limit, offset=offset
            ),
            _links=PageLinks(
                self=f"{request_url.replace_query_params(offset=offset, limit=limit)}",
                first=f"{request_url.replace_query_params(offset= 0, limit= limit)}",
                prev=f"{request_url.replace_query_params(offset= max(offset - limit, 0), limit= limit)}"
                if offset > 0
                else None,
                next=f"{request_url.replace_query_params(offset= min(offset + limit, last_page * limit), limit= limit)}"
                if offset < (last_page * limit)
                else None,
                last=f"{request_url.replace_query_params(offset= last_page * limit, limit= limit)}",
            ),
            data=data,
        )


# --------------


class State(BaseModel):
    ...


class Node(BaseModel):
    key: str
    version: str = Field(..., regex=r"\d+\.\d+\.\d+")
    label: str

    inputs: Dict[InputID, DataSchema]
    # var inputs?
    outputs: Dict[OutputID, DataSchema]
    # var outputs?


# --------------
class Project(BaseModel):
    """Domain model"""

    id: UUID
    pipeline: Dict[UUID, Node]


# requests models
class ProjectNew(BaseModel):
    pipeline: Dict[UUID, Node]


class ProjectUpdate(BaseModel):
    # same as new but ALL optional??
    # some validators?
    pass


# response models
class ProjectItem(BaseModel):
    # Lightweight and part of an array
    id: UUID

    url: HttpUrl


class ProjectDetail(BaseModel):
    id: UUID
    pipeline: Dict[UUID, Node]

    url: HttpUrl

    def update_ids(self, name: str):
        map_ids: Dict[UUID, UUID] = {}
        map_ids[self.id] = uuid3(self.id, name)
        map_ids.update({node_id: uuid3(node_id, name) for node_id in self.pipeline})

        # replace ALL references


# --------------


class Parameter(BaseModel):
    name: str
    value: BuiltinTypes

    node_id: UUID
    output_id: OutputID


# reponse models
class ParameterDetail(Parameter):
    url: HttpUrl
    # url_output: HttpUrl


########################### DEPENDENCIES #########################################


def get_reverse_url_mapper(request: Request) -> Callable:
    def reverse_url_mapper(name: str, **path_params: Any) -> str:
        return request.url_for(name, **path_params)

    return reverse_url_mapper


def init_pagination(item_cls: Type):
    PageType = Page[item_cls]

    def _get(
        request: Request,
        offset: PositiveInt = Query(
            0, description="index to the first item to return (pagination)"
        ),
        limit: int = Query(
            20,
            description="maximum number of items to return (pagination)",
            ge=1,
            le=50,
        ),
    ) -> PageType:
        empty_page: PageType = PageType.parse_obj(
            Page.create_obj([], request.url, total=0, limit=limit, offset=offset)
        )
        return empty_page

    return _get


########################### HELPERS #########################################


def redefine_operation_id_in_router(router: APIRouter, operation_id_prefix: str):
    for route in router.routes:
        if isinstance(route, APIRoute):
            assert isinstance(route.endpoint, FunctionType)  # nosec
            route.operation_id = f"{operation_id_prefix}.{route.endpoint.__name__}"


def create_app(routers: List[APIRouter]) -> FastAPI:
    app = FastAPI(docs_url="/dev/doc")

    for r in routers:
        app.include_router(r)

    # print(yaml.safe_dump(app.openapi()))
    # print("-"*100)

    with open(f"{CURRENT_FILENAME_STEM}-openapi.ignore.json", "wt") as f:
        json.dump(app.openapi(), f, indent=2)

    return app


####################################################################

# project resource --------

_PROJECTS: Dict[UUID, Project] = {}


def get_valid_project(project_uuid: UUID = PathParam(...)) -> UUID:
    if project_uuid not in _PROJECTS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project does not exists"
        )
    return project_uuid


project_routes = APIRouter(prefix="/projects", tags=["project"])


@project_routes.get("", response_model=Page[ProjectItem])
def list_projects(page=Depends(init_pagination(ProjectItem))):
    ...


@project_routes.post(
    "", response_model=Envelope[ProjectDetail], status_code=status.HTTP_201_CREATED
)
def create_project(project: ProjectNew):
    ...


@project_routes.get("/{project_uuid}", response_model=Envelope[ProjectDetail])
def get_project(pid: UUID = Depends(get_valid_project)):
    ...


@project_routes.put("/{project_uuid}", response_model=Envelope[ProjectDetail])
def replace_project(project: ProjectNew, pid: UUID = Depends(get_valid_project)):
    ...


@project_routes.patch("/{project_uuid}", response_model=Envelope[ProjectDetail])
def update_project(project: ProjectUpdate, pid: UUID = Depends(get_valid_project)):
    ...


@project_routes.delete(
    "/{project_uuid}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_project(pid: UUID = Depends(get_valid_project)):
    ...


@project_routes.post("/{project_uuid}:open")
def open_project(pid: UUID = Depends(get_valid_project)):
    ...


@project_routes.post("/{project_uuid}:start")
def start_project(use_cache: bool = True, pid: UUID = Depends(get_valid_project)):
    ...


@project_routes.post("/{project_uuid}:stop")
def stop_project(pid: UUID = Depends(get_valid_project)):
    ...


@project_routes.post("/{project_uuid}:close")
def close_project(pid: UUID = Depends(get_valid_project)):
    ...


redefine_operation_id_in_router(
    project_routes,
    operation_id_prefix=simcore_service_webserver.projects.projects_handlers.__name__,
)

# project states sub-resource --------

pr_state_routes = APIRouter(prefix="/projects/{project_uuid}", tags=["project"])


@pr_state_routes.get("/state", response_model=Envelope[State])
def get_project_state(pid: UUID = Depends(get_valid_project)):
    ...


redefine_operation_id_in_router(
    pr_state_routes,
    operation_id_prefix=simcore_service_webserver.projects.projects_handlers.__name__,
)

# project nodes sub-resource --------

project_nodes_routes = APIRouter(prefix="/projects/{project_uuid}", tags=["project"])


@project_nodes_routes.get("/nodes", response_model=Envelope[Node])
def get_project_node(pid: UUID = Depends(get_valid_project)):
    ...


redefine_operation_id_in_router(
    pr_state_routes,
    operation_id_prefix=simcore_service_webserver.projects.projects_node_handlers.__name__,
)


# project tags sub-resource --------
# here we use a different approach just to check
class Tags:
    routes = APIRouter(prefix="/projects/{project_uuid}", tags=["project"])

    @staticmethod
    @routes.put("/tags/{tag_id}")
    def replace(tag_id: int, pid: UUID = Depends(get_valid_project)):
        """Assigns a tag to a project"""
        ...

    @staticmethod
    @routes.delete(
        "/tags/{tag_id}",
        status_code=status.HTTP_204_NO_CONTENT,
    )
    def delete(tag_id: int, pid: UUID = Depends(get_valid_project)):
        """Un-assigns tag to a project"""
        ...


# project snapshot subresource --------
#  - analogous to a git-commit
#  - takes a snapshot of the current state of the project
#  - WILL NOT USE?

snapshot_routes = APIRouter(
    prefix="/projects/{project_uuid}/snapshots", tags=["project", "snapshot"]
)


@snapshot_routes.get(
    "",
    response_model=Page[SnapshotResource],
)
def list_snapshots(
    page=Depends(init_pagination(SnapshotResource)),
    pid: UUID = Depends(get_valid_project),
    url_for: Callable = Depends(get_reverse_url_mapper),
):
    """Lists all snapshots taken from a given project"""


@snapshot_routes.post(
    "",
    response_model=Envelope[SnapshotResource],
    status_code=status.HTTP_201_CREATED,
)
def create_snapshot(
    pid: UUID = Depends(get_valid_project),
    snapshot_label: Optional[str] = None,
    url_for: Callable = Depends(get_reverse_url_mapper),
):
    """Takes a snapshot of the project at this time"""
    # - hash parent_project as a mechanism to check changes
    # -


@snapshot_routes.get(
    "/{snapshot_id}",
    response_model=Envelope[SnapshotResource],
)
def get_snapshot(
    snapshot_id: PositiveInt,
    pid: UUID = Depends(get_valid_project),
    url_for: Callable = Depends(get_reverse_url_mapper),
):
    """Gets commit info for a given snapshot"""


@snapshot_routes.delete(
    "/{snapshot_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_snapshot(
    snapshot_id: PositiveInt,
    pid: UUID = Depends(get_valid_project),
):
    """Deletes both the commit and the project itself"""
    # delete a snapshot -> project deleted?
    # delete a project-snapshot -> delete snapshot


@snapshot_routes.patch(
    "/{snapshot_id}",
)
def update_snapshot_name(
    snapshot_id: PositiveInt,
    snapshot_name: str,
    pid: UUID = Depends(get_valid_project),
):
    ...


redefine_operation_id_in_router(
    snapshot_routes,
    operation_id_prefix=simcore_service_webserver.snapshots_api_handlers.__name__,
)


# project parametrization subresource --------

parameter_routes = APIRouter(
    prefix="/projects/{project_uuid}/parameters", tags=["project"]
)


@parameter_routes.get(
    "",
    response_model=Page[ParameterDetail],
)
def list_project_parameters(
    snapshot_id: str,
    pid: UUID = Depends(get_valid_project),
    url_for: Callable = Depends(get_reverse_url_mapper),
):
    """Lists all parameters in a project"""


# repositories
#
#  -  versions workbench subresource
#  - Like a git system but with a "single file": the project's workbench
#
# cd new-project
# git init
# git add new-project/workbench
#
# git commit -m "Some changes"
#
# git add new-project.workbench
#
#
# SEE
#  - http://git-scm.com/docs/git
#  - https://gandalf.readthedocs.io/en/latest/api.html
#  - https://github.com/hulu/restfulgit#readme
#


RepoRef = Union[UUID, str]  # :ref is the repository ref (commit, tag or branch)

# response models
class Repo(BaseModel):
    project_uuid: UUID
    url: HttpUrl


class CommitRef(BaseModel):
    sha: str  #
    url: HttpUrl


class Commit(CommitRef):
    author: Author
    created_at: datetime
    message: str
    parents: List[CommitRef]


class Tag(BaseModel):
    name: str = Field(..., description="Unique tag name")
    commit_ref: CommitRef

    url: HttpUrl


#
_PROJECTS_WITH_REPO = {}


def get_valid_repo(pid: UUID = Depends(get_valid_project)):
    if pid in _PROJECTS_WITH_REPO:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project does not has a repository",
        )
    return pid


repo_routes = APIRouter(prefix="/repos/projects", tags=["repository"])


@repo_routes.get(
    "",
    response_model=Page[Repo],
)
def list_repos(page=Depends(init_pagination(Repo))):
    ...


@repo_routes.post(
    "/{project_uuid}",
    response_model=Envelope[Repo],
    status_code=status.HTTP_201_CREATED,
)
def create_repo(
    pid: UUID = Depends(get_valid_project),
):
    """Creates a repo to version a project

    cd project_uuid
    git init
    git add new-project/workbench
    """


@repo_routes.post(
    "/{project_uuid}/workbench/commits",
    response_model=Envelope[Commit],
    status_code=status.HTTP_201_CREATED,
)
def create_commit(
    message: str,
    pid: UUID = Depends(get_valid_repo),
):
    """Commit current state of the workbench's project

    git commit -m "Some changes"
    """


@repo_routes.get(
    "/{project_uuid}/workbench/commits",
    response_model=Page[Commit],
)
def get_logs(
    ref: str,
    page=Depends(init_pagination(Commit)),
    pid: UUID = Depends(get_valid_repo),
):
    """Lists commits tree of the project"""


@repo_routes.post(
    "/{project_uuid}/workbench/commits/{ref_id}", response_model=Envelope[Commit]
)
def get_commit(
    ref_id: RepoRef = Field(
        ..., description="A repository ref (commit, tag or branch)"
    ),
    pid: UUID = Depends(get_valid_repo),
):
    ...


@repo_routes.patch(
    "/{project_uuid}/workbench/commits/{ref_id}", response_model=Envelope[Commit]
)
def update_commit_message(
    ref_id: RepoRef = Field(
        ..., description="A repository ref (commit, tag or branch)"
    ),
    message: str = ...,
    pid: UUID = Depends(get_valid_repo),
):
    ...


@repo_routes.post(
    "/{project_uuid}/workbench/commits/{ref_id}:checkout",
    response_model=Envelope[Commit],
)
def checkout(
    ref_id: RepoRef = Field(
        ..., description="A repository ref (commit, tag or branch)"
    ),
    pid: UUID = Depends(get_valid_repo),
):
    ...


# do not expose!?
def create_branch():
    ...


@repo_routes.get("/{project_uuid}/workbench/tags", response_model=Page[Tag])
def list_tags(
    page=Depends(init_pagination(Tag)),
    pid: UUID = Depends(get_valid_repo),
):
    ...


@repo_routes.post("/{project_uuid}/workbench/tags", response_model=Envelope[Tag])
def create_tag(
    commit_sha: RepoRef,
    tag_name: str,
    pid: UUID = Depends(get_valid_repo),
):
    ...


@repo_routes.get(
    "/{project_uuid}/workbench/tags/{ref_id}", response_model=Envelope[Tag]
)
def get_tag(
    ref_id: RepoRef = Field(..., description="A commit sha or a tag name"),
    pid: UUID = Depends(get_valid_repo),
):
    ...


@repo_routes.patch(
    "/{project_uuid}/workbench/tags/{ref_id}", response_model=Envelope[Tag]
)
def update_tag_name(
    ref_id: RepoRef = Field(..., description="A commit sha or a tag name"),
    new_tag_name: str = ...,
    pid: UUID = Depends(get_valid_repo),
):
    ...


@repo_routes.delete(
    "/{project_uuid}/workbench/tags/{tag_name}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_tag(
    tag_name: str,
    pid: UUID = Depends(get_valid_repo),
):
    ...


#####################################################
# uvicorn --reload projects_openapi_generator:the_app
the_app = create_app(
    routers=[
        project_routes,
        project_nodes_routes,
        pr_state_routes,
        snapshot_routes,
        parameter_routes,
        repo_routes,
    ]
)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("projects_openapi_generator:the_app", reload=True, log_level="debug")
