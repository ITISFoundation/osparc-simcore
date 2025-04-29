import logging

import sqlalchemy as sa
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.users import UserID
from pydantic import TypeAdapter
from simcore_postgres_database.models.groups import user_to_groups
from simcore_postgres_database.models.project_to_groups import project_to_groups
from simcore_postgres_database.models.projects import projects
from simcore_postgres_database.models.projects_to_jobs import projects_to_jobs
from simcore_postgres_database.models.projects_to_products import projects_to_products
from simcore_postgres_database.utils_repos import (
    get_columns_from_db_model,
    pass_or_acquire_connection,
    transaction_context,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncConnection

from ..db.base_repository import BaseRepository
from .models import ProjectDBGet, ProjectJobDBGet

_logger = logging.getLogger(__name__)


_PROJECT_DB_COLS = get_columns_from_db_model(
    projects,
    ProjectDBGet,
)


class ProjectJobsRepository(BaseRepository):

    async def set_project_as_job(
        self,
        connection: AsyncConnection | None = None,
        *,
        project_uuid: ProjectID,
        job_parent_resource_name: str,
    ) -> None:
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
            )

            await conn.execute(stmt)

    async def list_projects_marked_as_jobs(
        self,
        connection: AsyncConnection | None = None,
        *,
        product_name: ProductName,
        user_id: UserID,
        offset: int = 0,
        limit: int = 10,
        job_parent_resource_name_prefix: str | None = None,
    ) -> tuple[int, list[ProjectJobDBGet]]:
        """Lists projects marked as jobs for a specific user and product


        Arguments:
            product_name -- caller's context product identifier
            user_id -- caller's user identifier

        Keyword Arguments:
            job_parent_resource_name_prefix -- is a prefix to filter the `job_parent_resource_name`. The latter is a
                path-like string that contains a hierarchy of resources. An example of `job_parent_resource_name` is:
                `/solvers/simcore%2Fservices%2Fcomp%2Fisolve/releases/1.3.4/jobs/f622946d-fd29-35b9-a193-abdd1095167c`
                SEE services/api-server/src/simcore_service_api_server/models/api_resources.py (default: {None})

        Returns:
            total_count, list of projects marked as jobs
        """

        # Step 1: Get group IDs associated with the user
        user_groups_query = (
            sa.select(user_to_groups.c.gid)
            .where(user_to_groups.c.uid == user_id)
            .subquery()
        )

        # Step 2: Create access_query to filter projects based on product_name and read access
        access_query = (
            sa.select(projects_to_jobs)
            .select_from(
                projects_to_jobs.join(
                    projects_to_products,
                    projects_to_jobs.c.project_uuid
                    == projects_to_products.c.project_uuid,
                ).join(
                    project_to_groups,
                    projects_to_jobs.c.project_uuid == project_to_groups.c.project_uuid,
                )
            )
            .where(
                projects_to_products.c.product_name == product_name,
                project_to_groups.c.gid.in_(sa.select(user_groups_query.c.gid)),
                project_to_groups.c.read.is_(True),
                projects.c.workspace_id.is_(
                    # ONLY projects in private workspaces
                    None
                ),
            )
        )

        # Apply job_parent_resource_name_filter if provided
        if job_parent_resource_name_prefix:
            access_query = access_query.where(
                projects_to_jobs.c.job_parent_resource_name.like(
                    f"{job_parent_resource_name_prefix}%"
                )
            )

        # Convert access_query to a subquery
        base_query = access_query.subquery()

        # Step 3: Query to get the total count
        total_query = sa.select(sa.func.count()).select_from(base_query)

        # Step 4: Query to get the paginated list with full selection
        list_query = (
            sa.select(
                *_PROJECT_DB_COLS,
                projects.c.workbench,
                base_query.c.job_parent_resource_name,
            )
            .select_from(
                base_query.join(
                    projects,
                    projects.c.uuid == base_query.c.project_uuid,
                )
            )
            .order_by(
                projects.c.creation_date.desc(),  # latests first
                projects.c.id.desc(),
            )
            .limit(limit)
            .offset(offset)
        )

        # Step 5: Execute queries
        async with pass_or_acquire_connection(self.engine, connection) as conn:
            total_count = await conn.scalar(total_query)
            assert isinstance(total_count, int)  # nosec

            result = await conn.execute(list_query)
            projects_list = TypeAdapter(list[ProjectJobDBGet]).validate_python(
                result.fetchall()
            )

            return total_count, projects_list
