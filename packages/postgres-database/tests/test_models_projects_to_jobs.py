# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from collections.abc import Iterator

import pytest
import simcore_postgres_database.cli
import sqlalchemy as sa
import sqlalchemy.engine
from faker import Faker
from pytest_simcore.helpers import postgres_tools
from pytest_simcore.helpers.faker_factories import random_project
from simcore_postgres_database.models.projects import projects
from simcore_postgres_database.models.projects_to_jobs import projects_to_jobs
from sqlalchemy.dialects.postgresql import insert


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
        sample_projects = [
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
            ),
            random_project(
                faker,
                uuid="bf204942-007b-11ef-befd-0242ac114f07",
                name="studies/4b7a704a-007a-11ef-befd-0242ac114f07/jobs/bf204942-007b-11ef-befd-0242ac114f07",
                description="Valid project 2",
            ),
            random_project(
                faker,
                uuid="33333333-3333-3333-3333-333333333333",
                name="invalid/project/name",
                description="Invalid project",
            ),
        ]
        conn.execute(insert(projects).values(sample_projects))

    # Run upgrade to head! to populate
    simcore_postgres_database.cli.upgrade.callback("head")

    with sync_engine.connect() as conn:
        # Query the projects_to_jobs table
        result = conn.execute(sa.select(projects_to_jobs)).fetchall()

        # Assert only valid projects are added
        assert len(result) == 2
        assert {
            "project_uuid": "cd03450c-4c17-4c2c-85fd-0d951d7dcd5a",
            "job_name": "solvers/simcore%2Fservices%2Fcomp%2Fitis%2Fsleeper/releases/2.2.1/jobs/cd03450c-4c17-4c2c-85fd-0d951d7dcd5a",
        } in result
        assert {
            "project_uuid": "bf204942-007b-11ef-befd-0242ac114f07",
            "job_name": "studies/4b7a704a-007a-11ef-befd-0242ac114f07/jobs/bf204942-007b-11ef-befd-0242ac114f07",
        } in result
