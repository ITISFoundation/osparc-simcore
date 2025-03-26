import sqlalchemy as sa
import sqlalchemy.engine
from faker import Faker
from pytest_simcore.helpers.faker_factories import random_project
from simcore_postgres_database.models.projects import projects
from simcore_postgres_database.models.projects_to_jobs import projects_to_jobs
from sqlalchemy.dialects.postgresql import insert


def populate_projects_to_jobs(connection):
    """
    Populates the projects_to_jobs table by analyzing the projects table.


    NOTE: tested here but will be used in migration script
    """
    query = sa.text(
        """
        INSERT INTO projects_to_jobs (project_uuid, job_name, job_info)
        SELECT
            uuid AS project_uuid,
            regexp_replace(name, '^.*jobs/([^/]+)$', '\\1') AS job_name,
        FROM projects
        WHERE name ~* '^solvers/.+/jobs/.+$' OR name ~* '^studies/.+/jobs/.+$';
    """
    )
    connection.execute(query)


def test_populate_projects_to_jobs(
    pg_sa_engine: sqlalchemy.engine.Engine, faker: Faker
):

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

    # Insert sample projects into the projects table
    with pg_sa_engine.connect() as conn:
        conn.execute(insert(projects).values(sample_projects))

        # Run the populate_projects_to_jobs function
        populate_projects_to_jobs(conn)

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
