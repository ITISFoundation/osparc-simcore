from copy import deepcopy
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from pydantic import BaseModel

ProjectUUID = UUID
CommitID = str
TagID = str


class Commit(BaseModel):
    sha1: str


class Node(BaseModel):
    name: str


class Project(BaseModel):
    name: str
    uuid: UUID
    workbench: Dict[str, Any] = {}

    # version_control: Optional[VersionControl]


_PROJECTS: List[Project] = [
    Project(
        name="foo",
        uuid="5ede1cb3-9361-469f-a956-c5f15ac4d7f4",
    )
]
_COMMITS: List[Commit] = []


def _fetch_project(uuid: str):
    return next(p for p in _PROJECTS if p.uuid == UUID(uuid))


# GET /projects/{project_uuid}
# GET /projects/{project_uuid}/versioned/:repo_ref ??
def get_project(uuid: str, tag: Optional[str] = None, commit: Optional[str] = None):
    return deepcopy(_fetch_project(uuid))


def replace_project(uuid: str, project: Project):
    prj = _fetch_project(uuid)
    prj = project


def update_project(uuid: str, changes):
    pass


def get_project_workbench(
    uuid: str, *, tag: Optional[str] = None, commit: Optional[str] = None
):
    if not tag and not commit:
        # use working copy
        return deepcopy(_fetch_project(uuid).workbench)


# GET /repos/projects/{project_uuid}/commits
def list_commits(project_uuid: str):
    ...


# GET /repos/projects/{project_uuid}/commits/{rev_id}
def get_commit(project_uuid: str, rev_id: Union[CommitID, TagID]):
    ...


# GET /repos/projects/{project_uuid}/commits
def create_commit(
    project_uuid: str, *, message: Optional[str] = None, tag: Optional[str] = None
):
    # commit states of WC
    pass


# GET /repos/projects/{project_uuid}/commits/{rev_id}/workbench/view
def get_project_workbench_view(project_uuid: str, rev_id: Optional[str] = None):
    ...


# POST /repos/projects/{project_uuid}/commits/{rev_id}:checkout
def checkout(project_uuid: str, rev_id: Union[CommitID, TagID]):
    ...


############################################################################################


def test_it():

    # gets project working copy (WC)
    project = get_project("5ede1cb3-9361-469f-a956-c5f15ac4d7f4")

    # changes
    project.workbench["n1"] = Node(name="sleeper 1")

    # take snapshot (or 'add checkpoint')
    replace_project("5ede1cb3-9361-469f-a956-c5f15ac4d7f4", project)
    commit = create_commit("5ede1cb3-9361-469f-a956-c5f15ac4d7f4", tag="version 1")

    # auto-save
    project.workbench["n2"] = Node(name="sleeper 2")
    replace_project("5ede1cb3-9361-469f-a956-c5f15ac4d7f4", project)

    # get previous version

    # get_project("5ede1cb3-9361-469f-a956-c5f15ac4d7f4", tag="version 1").workbench
    # or simply
    workbench_v1 = get_project_workbench_view(
        "5ede1cb3-9361-469f-a956-c5f15ac4d7f4", tag="version 1"
    )

    # list all commits history (git log)
    commits = list_commits("5ede1cb3-9361-469f-a956-c5f15ac4d7f4")

    # changes the WC with snapshot tagged as version 1
    checkout("5ede1cb3-9361-469f-a956-c5f15ac4d7f4", "version 1")
    project_v1 = get_project("5ede1cb3-9361-469f-a956-c5f15ac4d7f4")

    commit = get_commit("5ede1cb3-9361-469f-a956-c5f15ac4d7f4")

    ## commit.tag == "version 1"


# def test_worklfow():

#     # create a new project
#     project = create_project(**project_params)
#     # - project is like a directory, and this is a git init in the directory
#     repo = init_repo(project.uuid)
#     commit_1 = repo.create_commit(message="init")

#     # auto save: user makes some more changes
#     update_project(project.uuid, **project_changes)

#     # clicks to create a checkpoint. adds a message and labels as 'foo'
#     # - check if any changes between WC and HEAD
#     # - make snapshot copy and creates commit sha1
#     commit_2 = repo.create_commit(message="some changes")
#     repo.create_tag(commit_2, name="foo")

#     # 4
#     update_project(project.uuid, even_more_project_changes)
#     commit_4 = repo.create_commit(message="some changes 4")
#     repo.create_tag(commit_4, name="foo")

#     # 5
#     update_project(project.uuid, even_more_project_changes)
#     head = get_commit(repo, "HEAD")

#     commit_foo = repo.checkout(tag="foo")
#     detached_project4 = get_project(commit_foo.project_uuid)

#     update_project(detached_project4.uuid, some_changes)
#     commit_4_1 = repo.create_commit(message="some changes 4.1")
