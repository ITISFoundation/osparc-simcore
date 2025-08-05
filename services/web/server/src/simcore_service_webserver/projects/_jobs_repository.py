import logging

import sqlalchemy as sa
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.users import UserID
from pydantic import TypeAdapter
from simcore_postgres_database.models.groups import user_to_groups
from simcore_postgres_database.models.project_to_groups import project_to_groups
from simcore_postgres_database.models.projects import projects
from simcore_postgres_database.models.projects_metadata import projects_metadata
from simcore_postgres_database.models.projects_nodes import projects_nodes
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


def _apply_job_parent_resource_name_filter(
    query: sa.sql.Select, prefix: str
) -> sa.sql.Select:
    return query.where(projects_to_jobs.c.job_parent_resource_name.like(f"{prefix}%"))


def _apply_custom_metadata_filter(
    query: sa.sql.Select, any_metadata_fields: list[tuple[str, str]]
) -> sa.sql.Select:
    """Apply metadata filters to query.

    For PostgreSQL JSONB fields, we need to extract the text value using ->> operator
    before applying string comparison operators like ILIKE.
    """
    assert any_metadata_fields  # nosec

    metadata_fields_ilike = []
    for key, pattern in any_metadata_fields:
        # Use ->> operator to extract the text value from JSONB
        # Then apply ILIKE for case-insensitive pattern matching
        sql_pattern = pattern.replace("*", "%")  # Convert glob-like pattern to SQL LIKE
        metadata_fields_ilike.append(
            projects_metadata.c.custom[key].astext.ilike(sql_pattern)
        )

    return query.where(sa.or_(*metadata_fields_ilike))


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
        pagination_offset: int,
        pagination_limit: int,
        filter_by_job_parent_resource_name_prefix: str | None = None,
        filter_any_custom_metadata: list[tuple[str, str]] | None = None,
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
                )
                .join(
                    project_to_groups,
                    projects_to_jobs.c.project_uuid == project_to_groups.c.project_uuid,
                )
                .join(
                    # NOTE: avoids `SAWarning: SELECT statement has a cartesian product ...`
                    projects,
                    projects_to_jobs.c.project_uuid == projects.c.uuid,
                )
                .outerjoin(
                    projects_metadata,
                    projects_to_jobs.c.project_uuid == projects_metadata.c.project_uuid,
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

        # Step 3: Apply filters
        if filter_by_job_parent_resource_name_prefix:
            access_query = _apply_job_parent_resource_name_filter(
                access_query, filter_by_job_parent_resource_name_prefix
            )

        if filter_any_custom_metadata:
            access_query = _apply_custom_metadata_filter(
                access_query, filter_any_custom_metadata
            )

        # Step 4. Convert access_query to a subquery
        base_query = access_query.subquery()

        # Step 5: Query to get the total count
        total_query = sa.select(sa.func.count()).select_from(base_query)

        # Step 6: Create subquery to aggregate project nodes into workbench structure
        workbench_subquery = (
            sa.select(
                projects_nodes.c.project_uuid,
                sa.func.json_object_agg(
                    projects_nodes.c.node_id,
                    sa.func.json_build_object(
                        "key",
                        projects_nodes.c.key,
                        "version",
                        projects_nodes.c.version,
                        "label",
                        projects_nodes.c.label,
                        "progress",
                        projects_nodes.c.progress,
                        "thumbnail",
                        projects_nodes.c.thumbnail,
                        "inputAccess",
                        projects_nodes.c.input_access,
                        "inputNodes",
                        projects_nodes.c.input_nodes,
                        "inputs",
                        projects_nodes.c.inputs,
                        "inputsRequired",
                        projects_nodes.c.inputs_required,
                        "inputsUnits",
                        projects_nodes.c.inputs_units,
                        "outputNodes",
                        projects_nodes.c.output_nodes,
                        "outputs",
                        projects_nodes.c.outputs,
                        "runHash",
                        projects_nodes.c.run_hash,
                        "state",
                        projects_nodes.c.state,
                        "parent",
                        projects_nodes.c.parent,
                        "bootOptions",
                        projects_nodes.c.boot_options,
                    ),
                ).label("workbench"),
            )
            .group_by(projects_nodes.c.project_uuid)
            .subquery()
        )

        # Step 7: Query to get the paginated list with full selection
        list_query = (
            sa.select(
                *_PROJECT_DB_COLS,
                sa.func.coalesce(
                    workbench_subquery.c.workbench, sa.text("'{}'::json")
                ).label("workbench"),
                base_query.c.job_parent_resource_name,
            )
            .select_from(
                base_query.join(
                    projects,
                    projects.c.uuid == base_query.c.project_uuid,
                ).outerjoin(
                    workbench_subquery,
                    projects.c.uuid == workbench_subquery.c.project_uuid,
                )
            )
            .order_by(
                projects.c.creation_date.desc(),  # latests first
                projects.c.id.desc(),
            )
            .limit(pagination_limit)
            .offset(pagination_offset)
        )

        # Step 8: Execute queries
        async with pass_or_acquire_connection(self.engine, connection) as conn:
            total_count = await conn.scalar(total_query)
            assert isinstance(total_count, int)  # nosec

            result = await conn.execute(list_query)
            projects_list = TypeAdapter(list[ProjectJobDBGet]).validate_python(
                result.fetchall()
            )

            return total_count, projects_list
