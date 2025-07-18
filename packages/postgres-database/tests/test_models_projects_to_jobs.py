# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from collections.abc import Iterator

import pytest
import simcore_postgres_database.cli
import sqlalchemy as sa
import sqlalchemy.engine
import sqlalchemy.exc
from common_library.users_enums import UserRole
from faker import Faker
from pytest_simcore.helpers import postgres_tools
from pytest_simcore.helpers.faker_factories import random_project, random_user
from simcore_postgres_database.models.projects import projects
from simcore_postgres_database.models.projects_to_jobs import projects_to_jobs


@pytest.fixture
def sync_engine(
    sync_engine: sqlalchemy.engine.Engine, db_metadata: sa.MetaData
) -> Iterator[sqlalchemy.engine.Engine]:
    # EXTENDS sync_engine fixture to include cleanup and parare migration

    # cleanup tables
    db_metadata.drop_all(sync_engine)

    # prepare migration upgrade
    assert simcore_postgres_database.cli.discover.callback
    assert simcore_postgres_database.cli.upgrade.callback

    dsn = sync_engine.url
    simcore_postgres_database.cli.discover.callback(
        user=dsn.username,
        password=dsn.password,
        host=dsn.host,
        database=dsn.database,
        port=dsn.port,
    )

    yield sync_engine

    # cleanup tables
    postgres_tools.force_drop_all_tables(sync_engine)


def test_populate_projects_to_jobs_during_migration(
    sync_engine: sqlalchemy.engine.Engine, faker: Faker
):
    assert simcore_postgres_database.cli.discover.callback
    assert simcore_postgres_database.cli.upgrade.callback

    # UPGRADE just one before 48604dfdc5f4_new_projects_to_job_map.py
    simcore_postgres_database.cli.upgrade.callback("8403acca8759")

    with sync_engine.connect() as conn:

        # Ensure the projects_to_jobs table does NOT exist yet
        with pytest.raises(sqlalchemy.exc.ProgrammingError) as exc_info:
            conn.execute(
                sa.select(sa.func.count()).select_from(projects_to_jobs)
            ).scalar()
        assert "psycopg2.errors.UndefinedTable" in f"{exc_info.value}"

        # INSERT data (emulates data in-place)
        user_data = random_user(
            faker,
            name="test_populate_projects_to_jobs_during_migration",
            role=UserRole.USER.value,
        )
        user_data["password_hash"] = (
            "password_hash_was_still_here_at_this_migration_commit"  # noqa: S105
        )

        columns = list(user_data.keys())
        values_clause = ", ".join(f":{col}" for col in columns)
        columns_clause = ", ".join(columns)
        stmt = sa.text(
            f"""
            INSERT INTO users ({columns_clause})
            VALUES ({values_clause})
            RETURNING id
            """  # noqa: S608
        ).bindparams(**user_data)
        result = conn.execute(stmt)
        user_id = result.scalar()

        SPACES = " " * 3
        projects_data = [
            random_project(
                faker,
                uuid="cd03450c-4c17-4c2c-85fd-0d951d7dcd5a",
                name="solvers/simcore%2Fservices%2Fcomp%2Fitis%2Fsleeper/releases/2.2.1/jobs/cd03450c-4c17-4c2c-85fd-0d951d7dcd5a",
                description=(
                    "Study associated to solver job:"
                    """{
                    "id": "cd03450c-4c17-4c2c-85fd-0d951d7dcd5a",
                    "name": "solvers/simcore%2Fservices%2Fcomp%2Fitis%2Fsleeper/releases/2.2.1/jobs/cd03450c-4c2c-85fd-0d951d7dcd5a",
                    "inputs_checksum": "015ba4cd5cf00c511a8217deb65c242e3b15dc6ae4b1ecf94982d693887d9e8a",
                    "created_at": "2025-01-27T13:12:58.676564Z"
                    }
                    """
                ),
                prj_owner=user_id,
            ),
            random_project(
                faker,
                uuid="bf204942-007b-11ef-befd-0242ac114f07",
                name=f"studies/4b7a704a-007a-11ef-befd-0242ac114f07/jobs/bf204942-007b-11ef-befd-0242ac114f07{SPACES}",
                description="Valid project 2",
                prj_owner=user_id,
            ),
            random_project(
                faker,
                uuid="33333333-3333-3333-3333-333333333333",
                name="invalid/project/name",
                description="Invalid project",
                prj_owner=user_id,
            ),
        ]
        for prj in projects_data:
            conn.execute(sa.insert(projects).values(prj))

    # MIGRATE UPGRADE: this should populate
    simcore_postgres_database.cli.upgrade.callback("head")

    with sync_engine.connect() as conn:
        # Query the projects_to_jobs table
        result = conn.execute(
            sa.select(
                projects_to_jobs.c.project_uuid,
                projects_to_jobs.c.job_parent_resource_name,
            )
        ).fetchall()

        # Assert only valid projects are added
        assert len(result) == 2
        assert (
            "cd03450c-4c17-4c2c-85fd-0d951d7dcd5a",
            "solvers/simcore%2Fservices%2Fcomp%2Fitis%2Fsleeper/releases/2.2.1",
        ) in result
        assert (
            "bf204942-007b-11ef-befd-0242ac114f07",
            "studies/4b7a704a-007a-11ef-befd-0242ac114f07",
        ) in result

        # Query project name and description for projects also in projects_to_jobs
        result = conn.execute(
            sa.select(
                projects.c.name,
                projects.c.uuid,
                projects_to_jobs.c.job_parent_resource_name,
            ).select_from(
                projects.join(
                    projects_to_jobs, projects.c.uuid == projects_to_jobs.c.project_uuid
                )
            )
        ).fetchall()

        # Print or assert the result as needed
        for project_name, project_uuid, job_parent_resource_name in result:
            assert (
                f"{job_parent_resource_name}/jobs/{project_uuid}"
                == project_name.strip()
            )
