# pylint: disable=no-value-for-parameter
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from copy import deepcopy
from typing import Optional
from uuid import UUID, uuid3

import pytest
from aiopg.sa.engine import Engine
from aiopg.sa.result import ResultProxy, RowProxy
from pytest_simcore.helpers.rawdata_fakers import random_project, random_user
from simcore_postgres_database.models.projects import projects
from simcore_postgres_database.models.snapshots import snapshots
from simcore_postgres_database.models.users import users

USERNAME = "me"
PARENT_PROJECT_NAME = "parent"


def test_it():
    import os

    cwd = os.getcwd()

    assert True


@pytest.fixture
async def engine(pg_engine: Engine):
    # injects ...
    async with pg_engine.acquire() as conn:
        # a 'me' user
        user_id = await conn.scalar(
            users.insert().values(**random_user(name=USERNAME)).returning(users.c.id)
        )
        # has a project 'parent'
        await conn.execute(
            projects.insert().values(
                **random_project(prj_owner=user_id, name=PARENT_PROJECT_NAME)
            )
        )
    yield pg_engine


async def test_creating_snapshots(engine: Engine):
    exclude = {
        "id",
        "uuid",
        "creation_date",
        "last_change_date",
        "hidden",
        "published",
    }

    async def _create_snapshot(child_index: int, parent_prj, conn) -> int:
        # create project-snapshot
        prj_dict = {c: deepcopy(parent_prj[c]) for c in parent_prj if c not in exclude}

        prj_dict["name"] += f" [snapshot {child_index}]"
        prj_dict["uuid"] = uuid3(UUID(parent_prj.uuid), f"snapshot.{child_index}")
        # creation_data = state of parent upon copy! WARNING: changes can be state changes and not project definition?
        prj_dict["creation_date"] = parent_prj.last_change_date
        prj_dict["hidden"] = True
        prj_dict["published"] = False

        # NOTE: a snapshot has no results but workbench stores some states,
        #  - input hashes
        #  - node ids

        #
        # Define policies about changes in parent project and
        # how it influence children
        #
        project_uuid: str = await conn.scalar(
            projects.insert().values(**prj_dict).returning(projects.c.uuid)
        )

        assert UUID(project_uuid) == prj_dict["uuid"]

        # create snapshot
        snapshot_id = await conn.scalar(
            snapshots.insert()
            .values(
                name=f"Snapshot {child_index}",
                parent_uuid=parent_prj.uuid,
                child_index=child_index,
                project_uuid=project_uuid,
            )
            .returning(snapshots.c.id)
        )
        return snapshot_id

    async with engine.acquire() as conn:

        # get parent
        res: ResultProxy = await conn.execute(
            projects.select().where(projects.c.name == PARENT_PROJECT_NAME)
        )
        parent_prj: Optional[RowProxy] = await res.first()

        assert parent_prj

        # take one snapshot
        snapshot_one_id = await _create_snapshot(0, parent_prj, conn)

        # modify parent
        updated_parent_prj = await (
            await conn.execute(
                projects.update()
                .values(description="foo")
                .where(projects.c.id == parent_prj.id)
                .returning(projects)
            )
        ).first()

        assert updated_parent_prj
        assert updated_parent_prj.id == parent_prj.id
        assert updated_parent_prj.description != parent_prj.description
        assert updated_parent_prj.creation_date < updated_parent_prj.last_change_date

        # take another snapshot
        snapshot_two_id = await _create_snapshot(1, updated_parent_prj, conn)

        snapshot_two = await (
            await conn.execute(
                snapshots.select().where(snapshots.c.id == snapshot_two_id)
            )
        ).first()

        assert snapshot_two.id != snapshot_one_id
        assert snapshot_two.created_at == updated_parent_prj.last_change_date

        # get project corresponding to snapshot 1
        j = projects.join(snapshots, projects.c.uuid == snapshots.c.project_uuid)
        selected_snapshot_project = await (
            await conn.execute(
                projects.select()
                .select_from(j)
                .where(snapshots.c.id == snapshot_two_id)
            )
        ).first()

        assert selected_snapshot_project
        assert selected_snapshot_project.uuid == snapshot_two.projects_uuid
        assert parent_prj.uuid == snapshot_two.parent_uuid

        def extract(t):
            return {k: t[k] for k in t if k not in exclude.union({"name"})}

        assert extract(selected_snapshot_project) == extract(updated_parent_prj)

        # TODO: if we call to take consecutive snapshots ... of the same thing, it should
        # return existing


def test_deleting_snapshots():
    # test delete child project -> deletes snapshot
    # test delete snapshot -> deletes child project

    # test delete parent project -> deletes snapshots
    # test delete snapshot does NOT delete parent
    pass


def test_create_pydantic_models_from_sqlalchemy_tables():
    # SEE https://docs.sqlalchemy.org/en/14/core/metadata.html
    # SEE https://github.com/tiangolo/pydantic-sqlalchemy/blob/master/pydantic_sqlalchemy/main.py
    pass
