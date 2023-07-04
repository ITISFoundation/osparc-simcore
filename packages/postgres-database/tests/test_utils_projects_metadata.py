# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

import pytest
import sqlalchemy as sa
from aiopg.sa.connection import SAConnection
from aiopg.sa.result import ResultProxy, RowProxy
from simcore_postgres_database.models.projects import projects
from simcore_postgres_database.models.projects_metadata import (
    projects_jobs_metadata,
    projects_metadata,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert


@pytest.fixture
async def fake_user(
    connection: SAConnection,
    create_fake_user: Callable[..., Awaitable[RowProxy]],
) -> RowProxy:
    user: RowProxy = await create_fake_user(connection, name=f"user.{__name__}")
    return user


@pytest.fixture
async def fake_project(
    connection: SAConnection,
    fake_user: RowProxy,
    create_fake_project: Callable[..., Awaitable[RowProxy]],
) -> RowProxy:
    project: RowProxy = await create_fake_project(connection, fake_user, hidden=True)
    return project


async def test_jobs_workflow(
    connection: SAConnection,
    create_fake_project: Callable[..., Awaitable[RowProxy]],
    create_fake_user: Callable[..., Awaitable[RowProxy]],
):
    user: RowProxy = await create_fake_user(connection)

    async def _create_solver_job(service_key: str, service_version: str, n: int):
        parent_name = f"/v0/solvers/{service_key}/releases/{service_version}"
        project: RowProxy = await create_fake_project(connection, user, hidden=True)

        query = projects_jobs_metadata.insert().values(
            project_uuid=project.uuid,
            parent_name=parent_name,
            job_metadata={
                "__type__": "JobMeta",
                "inputs_checksum": f"{n}2bfd4885aa1daf5c16fdd39b9118f652c4977c4021c900794dc125cf123718e",
                "created_at": f"2022-06-01T15:{n}:56.807441",
            },
        )
        result: ResultProxy = await connection.execute(query)
        assert result
        return project.uuid

    # some project from the UI
    project_study = await create_fake_project(connection, user, hidden=True)

    # CREATE
    # some solver-job projects
    created_jobs: list[UUID] = [
        await _create_solver_job(
            service_key="simcore/comp/itis/sleeper", service_version="2.0.0", n=n
        )
        for n in range(3)
    ]

    assert project_study.uuid not in set(created_jobs)

    # READ
    async def _list_solver_jobs(service_key: str, service_version: str):
        # list jobs of a solver
        parent_name = f"/v0/solvers/{service_key}/releases/{service_version}"

        j = projects.join(
            projects_jobs_metadata,
            (projects.c.uuid == projects_jobs_metadata.c.project_uuid),
        )
        query = (
            sa.select(projects_jobs_metadata, projects.c.hidden)
            .select_from(j)
            .where(projects_jobs_metadata.c.parent_name == parent_name)
        )
        jobs = await (await connection.execute(query)).fetchall()
        assert jobs
        return jobs

    got_jobs = await _list_solver_jobs(
        service_key="simcore/comp/itis/sleeper", service_version="2.0.0"
    )
    assert {j.project_uuid for j in got_jobs} == set(created_jobs)
    assert all(j.hidden for j in got_jobs)

    # list jobs of a study
    # list all jobs of a user
    # list projects that are non-jobs

    async def _upsert_custom_metadata(project_uuid, metadata: dict[str, Any]):
        params = dict(
            project_uuid=f"{project_uuid}",
            custom_metadata=metadata,
        )
        insert_stmt = pg_insert(projects_metadata).values(**params)
        on_update_stmt = insert_stmt.on_conflict_do_update(
            index_elements=[
                projects_metadata.c.project_uuid,
            ],
            set_=params,
        )
        await connection.execute(on_update_stmt)

    # UPDATE custom - meta
    await _upsert_custom_metadata(project_study.uuid, metadata={"my data": "foo"})
    await _upsert_custom_metadata(
        got_jobs[0].project_uuid, metadata={"jobs data": "bar"}
    )

    # DELETE job by deleting project


# test create a job
#
#    - from a study
#    - from a solver
# - search jobs from a study, from a solver, etc
# - list studies  -> projects uuids that are not jobs
# - list study jobs -> projects uuids that are Jodbs
