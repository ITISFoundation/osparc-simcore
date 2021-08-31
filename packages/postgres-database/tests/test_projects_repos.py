# pylint: disable=no-value-for-parameter
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from copy import deepcopy
from typing import Callable, List, Optional, Set, Tuple
from uuid import UUID, uuid3

import pytest
from aiopg.sa.connection import SAConnection
from aiopg.sa.engine import Engine
from aiopg.sa.result import RowProxy
from pytest_simcore.helpers.rawdata_fakers import random_project, random_user
from simcore_postgres_database.models.projects import projects
from simcore_postgres_database.models.projects_repos import (
    projects_checkpoints,
    projects_repos,
)
from simcore_postgres_database.models.users import users
from simcore_postgres_database.utils_version_control import (
    ProjectRepository,
    SHA1Str,
    add_to_staging,
    commit,
)

USERNAME = f"{__file__}-user"
PARENT_PROJECT_NAME = f"{__file__}-project"


@pytest.fixture
async def conn(pg_engine: Engine) -> SAConnection:
    async with pg_engine.acquire() as _conn:
        yield _conn


@pytest.fixture
async def fake_project(pg_engine: Engine) -> RowProxy:
    # injects ...
    async with pg_engine.acquire() as conn:
        # a 'me' user
        user_id = await conn.scalar(
            users.insert().values(**random_user(name=USERNAME)).returning(users.c.id)
        )
        # has a project 'parent'
        prj = await (
            await conn.execute(
                projects.insert()
                .values(**random_project(prj_owner=user_id, name=PARENT_PROJECT_NAME))
                .returning(projects)
            )
        ).first()
        assert prj is not None
        return prj


EXCLUDE = {
    "id",
    "uuid",
    "creation_date",
    "last_change_date",
    "hidden",
    "published",
}


#####################


def eval_checksum(item) -> SHA1Str:
    # pipeline = OrderedDict((key, Node(**value)) for key, value in workbench.items())
    # FIXME:  implement checksum

    # NOTE: must capture changes in the workbnehc despite possible changes in the uuids
    return "1" * 40


async def clone_as_snapshot(
    project: RowProxy, repo_id: int, snapshot_checksum: str, conn: SAConnection
):
    # create project-snapshot
    snapshot = {c: deepcopy(project[c]) for c in project if c not in EXCLUDE}

    snapshot["name"] = f"snapshot.{repo_id}.{snapshot_checksum}"
    snapshot["uuid"] = snapshot_uuid = str(
        uuid3(UUID(project.uuid), f"{repo_id}.{snapshot_checksum}")
    )
    # creation_data = state of parent upon copy! WARNING: changes can be state changes and not project definition?
    snapshot["creation_date"] = project.last_change_date
    snapshot["hidden"] = True
    snapshot["published"] = False

    # NOTE: a snapshot has no results but workbench stores some states,
    #  - input hashes
    #  - node ids

    query = projects.insert().values(**snapshot).returning(projects)
    snapshot_project: Optional[RowProxy] = await (await conn.execute(query)).first()
    assert snapshot_project
    assert snapshot_project.uuid == snapshot_uuid
    return snapshot_project


#####################


async def test_it(fake_project: RowProxy, conn: SAConnection):
    ## https://git-scm.com/book/en/v2/Git-Internals-Git-Objects

    wc_uuid = fake_project.uuid

    # init repo
    repo = ProjectRepository.create_repo(wc_uuid, conn)

    # hash wc

    # add  : stages the file
    # commit(tag: Optional[], message:, author: (auto) )

    # git logs

    # get ref/heads/{branch:main}

    # get ref/heads/tags/{:tag}

    # get ref/HEAD -> current head

    # set ref/heads/tags/{:tag} -> commit_id


# async def test_create_project_repo(fake_project: RowProxy, pg_engine: Engine):
@pytest.mark.skip(reason="UNDER DEVELOPMENT")
async def test_it2(fake_project: RowProxy, conn: SAConnection):

    wc_uuid = fake_project.uuid

    async with conn.begin():
        # create repo
        repo_id = await conn.scalar(
            projects_repos.insert()
            .values(project_uuid=wc_uuid)
            .returning(projects_repos.c.id)
        )
        assert repo_id

        # create first commit
        snapshot_checksum, snapshot_uuid, any_changes = await create_snapshot(
            repo_id, wc_uuid, conn
        )

        assert not any_changes
        head_id = await conn.scalar(
            projects_checkpoints.insert()
            .values(
                repo_id=repo_id,
                parent=None,
                tag="init",
                message="first commit",
                snapshot_checksum=snapshot_checksum,
                snapshot_uuid=snapshot_uuid,
            )
            .returning(projects_checkpoints.c.id)
        )

        await conn.execute(
            projects_repos.update()
            .where(projects_repos.c.id == repo_id)
            .values(head=head_id)
        )

    async with conn.begin():
        # detect no changes
        snapshot_checksum1, snapshot_uuid1, is_commited = await create_snapshot(
            repo_id, fake_project.uuid, conn
        )

        assert is_commited

    async with conn.begin():
        # changes
        assert fake_project.workbench == {}

        await conn.execute(
            projects.update()
            .where(projects.c.uuid == fake_project.uuid)
            .values(workbench={"uuid": {}})
        )

        # add changes
        snapshot_checksum, snapshot_uuid, any_changes = await create_snapshot(
            repo_id, wc_uuid, conn
        )

        # commit changes
        if any_changes:
            commit_id = await commit_staging(
                repo_id, snapshot_checksum, snapshot_uuid, conn
            )

    async with conn.begin():
        # checkout
        ...
