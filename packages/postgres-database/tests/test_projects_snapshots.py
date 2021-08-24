# pylint: disable=no-value-for-parameter
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from copy import deepcopy
from typing import Callable, Coroutine, Optional, Set
from uuid import UUID, uuid3

import pytest
from aiopg.sa.engine import Engine
from aiopg.sa.result import ResultProxy, RowProxy
from pytest_simcore.helpers.rawdata_fakers import random_project, random_user
from simcore_postgres_database.errors import UniqueViolation
from simcore_postgres_database.models.projects import projects
from simcore_postgres_database.models.projects_snapshots import projects_snapshots
from simcore_postgres_database.models.users import users

USERNAME = "me"
PARENT_PROJECT_NAME = "parent"


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


@pytest.fixture
def exclude() -> Set:
    return {
        "id",
        "uuid",
        "creation_date",
        "last_change_date",
        "hidden",
        "published",
    }


@pytest.fixture
def create_snapshot(exclude: Set) -> Coroutine:
    async def _create_snapshot(child_index: int, parent_prj, conn) -> int:
        # NOTE: used as FAKE prototype

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
            projects_snapshots.insert()
            .values(
                name=f"Snapshot {child_index} [{parent_prj.name}]",
                created_at=parent_prj.last_change_date,
                parent_uuid=parent_prj.uuid,
                project_uuid=project_uuid,
            )
            .returning(projects_snapshots.c.id)
        )
        return snapshot_id

    return _create_snapshot


async def test_creating_snapshots(
    engine: Engine, create_snapshot: Callable, exclude: Set
):

    async with engine.acquire() as conn:
        # get parent
        res: ResultProxy = await conn.execute(
            projects.select().where(projects.c.name == PARENT_PROJECT_NAME)
        )
        parent_prj: Optional[RowProxy] = await res.first()

        assert parent_prj

        # take one snapshot
        first_snapshot_id = await create_snapshot(0, parent_prj, conn)

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
        second_snapshot_id = await create_snapshot(1, updated_parent_prj, conn)

        second_snapshot = await (
            await conn.execute(
                projects_snapshots.select().where(
                    projects_snapshots.c.id == second_snapshot_id
                )
            )
        ).first()

        assert second_snapshot
        assert second_snapshot.id != first_snapshot_id
        assert second_snapshot.created_at == updated_parent_prj.last_change_date

        # get project corresponding to first snapshot
        j = projects.join(
            projects_snapshots, projects.c.uuid == projects_snapshots.c.project_uuid
        )
        selected_snapshot_project = await (
            await conn.execute(
                projects.select()
                .select_from(j)
                .where(projects_snapshots.c.id == second_snapshot_id)
            )
        ).first()

        assert selected_snapshot_project
        assert selected_snapshot_project.uuid == second_snapshot.project_uuid
        assert parent_prj.uuid == second_snapshot.parent_uuid

        def extract(t):
            return {k: t[k] for k in t if k not in exclude.union({"name"})}

        assert extract(selected_snapshot_project) == extract(updated_parent_prj)

        # TODO: if we call to take consecutive snapshots ... of the same thing, it should
        # return existing


async def test_multiple_snapshots_of_same_project(
    engine: Engine, create_snapshot: Callable
):
    async with engine.acquire() as conn:
        # get parent
        res: ResultProxy = await conn.execute(
            projects.select().where(projects.c.name == PARENT_PROJECT_NAME)
        )
        parent_prj: Optional[RowProxy] = await res.first()
        assert parent_prj

        # take first snapshot
        await create_snapshot(0, parent_prj, conn)

        # no changes in the parent!
        with pytest.raises(UniqueViolation):
            await create_snapshot(1, parent_prj, conn)
