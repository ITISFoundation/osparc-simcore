import datetime
import uuid
from dataclasses import dataclass
from typing import Any

import sqlalchemy as sa
from aiopg.sa.connection import SAConnection
from aiopg.sa.results import ResultProxy
from simcore_postgres_database.models.projects_metadata import projects_jobs_metadata

from .errors import ForeignKeyViolation
from .utils_models import FromRowMixin

#
# Errors
#


class ProjectNotFoundError(Exception):
    code = "projects.not_found"


class BaseProjectJobMetadataError(Exception):
    ...


class ProjectJobMetadataNotFoundError(BaseProjectJobMetadataError):
    code = "projects.job_metadata.not_found"


#
# Data
#


@dataclass(frozen=True, slots=True, kw_only=True)
class ProjectJobMetadata(FromRowMixin):
    project_uuid: uuid.UUID
    parent_name: str
    job_metadata: dict[str, Any] = {}
    created: datetime.datetime
    modified: datetime.datetime


#
# Repos
#


@dataclass(frozen=True, slots=True, kw_only=True)
class ProjectJobMetadataRepo:
    api_vtag: str = "v0"

    def _get_parent_name(
        self,
        service_key: str,
        service_version: str,
    ):
        return f"/{self.api_vtag}/solvers/{service_key}/releases/{service_version}"

    async def create_solver_job(
        self,
        connection: SAConnection,
        project_uuid: uuid.UUID,  # pk
        service_key: str,
        service_version: str,
        job_metadata: dict[str, Any] | None = None,
    ) -> ProjectJobMetadata:

        values: dict[str, Any] = {
            "project_uuid": project_uuid,
            "parent_name": self._get_parent_name(service_key, service_version),
        }
        if job_metadata:
            values["job_metadata"] = job_metadata

        try:
            insert_stmt = (
                projects_jobs_metadata.insert()
                .values(**values)
                .returning(*[projects_jobs_metadata.columns.keys()])
            )
            result: ResultProxy = await connection.execute(insert_stmt)
            row = await result.first()

            return ProjectJobMetadata.from_row(row)

        except ForeignKeyViolation as exc:
            msg = f"Cannot create metadata without a valid project {project_uuid=}"
            raise ProjectNotFoundError(msg) from exc

    async def list_solver_jobs(
        self,
        connection: SAConnection,
        service_key: str,
        service_version: str,
        limit: int,
        offset: int,
    ) -> list[ProjectJobMetadata]:
        assert limit > 0  # nosec
        assert offset >= 0  # nosec

        parent_name = self._get_parent_name(service_key, service_version)
        list_stmt = (
            sa.select(projects_jobs_metadata)
            .where(projects_jobs_metadata.c.parent_name == parent_name)
            .order_by(projects_jobs_metadata.c.created_at)
            .offset(offset)
            .limit(limit)
        )
        result: ResultProxy = await connection.execute(list_stmt)
        rows = await result.fetchall()
        return [ProjectJobMetadata.from_row(row) for row in rows]

    async def get(
        self, connection: SAConnection, project_uuid: uuid.UUID
    ) -> ProjectJobMetadata:
        get_stmt = sa.select(projects_jobs_metadata).where(
            projects_jobs_metadata.c.project_uuid == f"{project_uuid}"
        )
        result: ResultProxy = await connection.execute(get_stmt)
        if row := await result.first():
            return ProjectJobMetadata.from_row(row)
        raise ProjectJobMetadataNotFoundError

    async def update(
        self,
        connection: SAConnection,
        *,
        project_uuid: uuid.UUID,
        job_metadata: dict[str, Any],
    ) -> ProjectJobMetadata:

        update_stmt = (
            projects_jobs_metadata.update()
            .where(projects_jobs_metadata.c.project_uuid == project_uuid)
            .values(projects_jobs_metadata.c.job_metadata == job_metadata)
            .returning(*list(projects_jobs_metadata.columns))
        )
        result = await connection.execute(update_stmt)
        if row := await result.first():
            return ProjectJobMetadata.from_row(row)
        raise ProjectJobMetadataNotFoundError

    async def delete(self, connection: SAConnection, project_uuid: uuid.UUID) -> None:
        delete_stmt = sa.delete(projects_jobs_metadata).where(
            projects_jobs_metadata.c.project_uuid == f"{project_uuid}"
        )
        result = await connection.execute(delete_stmt)
        if result.rowcount:
            msg = f"Could not delete non-existing metadata of project_uuid={project_uuid!r}"
            raise ProjectJobMetadataNotFoundError(msg)
