import logging
from typing import cast

import sqlalchemy as sa
from pydantic import PositiveInt
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from .models.comp_runs import comp_runs
from .utils_repos import pass_or_acquire_connection

_logger = logging.getLogger(__name__)


async def get_latest_run_id_for_project(
    engine: AsyncEngine,
    conn: AsyncConnection | None = None,
    *,
    project_id: str,
) -> PositiveInt | None:
    # Get latest run per (project_uuid, user_id)
    project_and_user_latest_runs = (
        sa.select(
            comp_runs.c.project_uuid,
            comp_runs.c.user_id,
            sa.func.max(comp_runs.c.iteration).label("latest_iteration"),
            sa.func.max(comp_runs.c.created).label("created"),
        )
        .where(comp_runs.c.project_uuid == project_id)
        .group_by(comp_runs.c.project_uuid, comp_runs.c.user_id)
        .subquery("project_and_user_latest_runs")
    )

    # Rank users per project by latest run creation time
    ranked = sa.select(
        project_and_user_latest_runs.c.project_uuid,
        project_and_user_latest_runs.c.user_id,
        project_and_user_latest_runs.c.latest_iteration,
        project_and_user_latest_runs.c.created,
        sa.func.row_number()
        .over(
            partition_by=project_and_user_latest_runs.c.project_uuid,
            order_by=project_and_user_latest_runs.c.created.desc(),
        )
        .label("row_number"),
    ).subquery("ranked")

    # Filter to only the top-ranked (most recent) user per project
    filtered_ranked = (
        sa.select(
            ranked.c.project_uuid,
            ranked.c.user_id,
            ranked.c.latest_iteration,
        )
        .where(ranked.c.row_number == 1)
        .subquery("filtered_ranked")
    )

    # Base select query
    base_select_query = sa.select(comp_runs.c.run_id).select_from(
        filtered_ranked.join(
            comp_runs,
            sa.and_(
                comp_runs.c.project_uuid == filtered_ranked.c.project_uuid,
                comp_runs.c.user_id == filtered_ranked.c.user_id,
                comp_runs.c.iteration == filtered_ranked.c.latest_iteration,
            ),
        )
    )

    async with pass_or_acquire_connection(engine, connection=conn) as _conn:
        result = await _conn.execute(base_select_query)
        row = result.one_or_none()
        if not row:
            msg = f"get_latest_run_id_for_project did not return any row for project_id={project_id} (MD: I think this should not happen, but if it happens contact MD/SAN)"
            _logger.error(msg)
            return None
        return cast(PositiveInt, row.run_id)
