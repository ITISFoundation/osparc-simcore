import logging

from models_library.projects import ProjectID
from pydantic import PositiveInt
from simcore_postgres_database.models.projects_to_jobs import projects_to_jobs
from simcore_postgres_database.utils_repos import transaction_context
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncConnection

from ..db.base_repository import BaseRepository

_logger = logging.getLogger(__name__)


class ProjectJobsRepository(BaseRepository):

    async def set_project_as_job(
        self,
        connection: AsyncConnection | None = None,
        *,
        project_uuid: ProjectID,
        job_parent_resource_name: str,
    ) -> PositiveInt:
        async with transaction_context(self.engine, connection) as conn:
            stmt = (
                pg_insert(projects_to_jobs)
                .values(
                    project_uuid=f"{project_uuid}",
                    job_parent_resource_name=job_parent_resource_name,
                )
                .on_conflict_do_update(
                    index_elements=["project_uuid", "job_parent_resource_name"],
                    set_={"job_parent_resource_name": job_parent_resource_name},
                )
                .returning(projects_to_jobs.c.id)
            )

            result = await conn.execute(stmt)
            row = result.one()
            projects_to_jobs_id: PositiveInt = row.int
            return projects_to_jobs_id
