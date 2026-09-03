"""Applies a node's outputs/state change, regardless of whether it was reported
via the legacy DB-relay (Postgres NOTIFY) path or a direct RabbitMQ publish from
a modern producer (dynamic-sidecar, director-v2).

Always re-reads the authoritative comp_tasks row rather than trusting any
embedded values: this makes the handler safe to invoke out-of-order or more
than once for the same underlying change (see NodeDataUpdatedEventMessage docstring).
"""

import logging
from typing import Literal

from aiohttp import web
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.projects_state import RunningState
from models_library.users import UserID
from simcore_postgres_database.models.comp_tasks import comp_tasks
from sqlalchemy.engine import Row
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.sql import select

from ..db.plugin import get_asyncpg_engine
from ..projects import _projects_service, exceptions
from ..projects.nodes_utils import update_node_outputs
from ._utils import convert_state_from_db

_logger = logging.getLogger(__name__)


async def _get_comp_task_row(conn: AsyncConnection, project_id: ProjectID, node_id: NodeID) -> Row | None:
    result = await conn.execute(
        select(comp_tasks).where((comp_tasks.c.project_id == f"{project_id}") & (comp_tasks.c.node_id == f"{node_id}"))
    )
    return result.fetchone()


async def _update_project_state(
    app: web.Application,
    user_id: UserID,
    project_uuid: ProjectID,
    node_uuid: NodeID,
    new_state: RunningState,
) -> None:
    project = await _projects_service.update_project_node_state(
        app,
        user_id,
        project_uuid,
        node_uuid,
        new_state,
        client_session_id=None,  # <-- The trigger for this update is not from the UI
    )

    await _projects_service.notify_project_node_update(app, project, node_uuid)

    await _projects_service.notify_project_state_update(app, project)


async def apply_node_data_update(
    app: web.Application,
    *,
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
    changes: list[Literal["outputs", "state"]],
) -> None:
    try:
        engine = get_asyncpg_engine(app)
        async with engine.connect() as conn:
            changed_row = await _get_comp_task_row(conn, project_id, node_id)

        if not changed_row:
            _logger.warning(
                "No comp_tasks row found for project_id=%s node_id=%s",
                project_id,
                node_id,
            )
            return

        if "outputs" in changes:
            await update_node_outputs(
                app,
                user_id,
                project_id,
                node_id,
                changed_row.outputs,
                changed_row.run_hash,
                ui_changed_keys=None,
                client_session_id=None,  # <-- The trigger for this update is not from the UI
            )

        if "state" in changes and (changed_row.state is not None):
            await _update_project_state(
                app,
                user_id,
                project_id,
                node_id,
                convert_state_from_db(changed_row.state),
            )

    except exceptions.ProjectNotFoundError as exc:
        _logger.warning(
            "Project %s was not found and cannot be updated. Maybe was it deleted?",
            exc.project_uuid,
        )
    except exceptions.NodeNotFoundError as exc:
        _logger.warning(
            "Node %s of project %s not found and cannot be updated. Maybe was it deleted?",
            exc.node_uuid,
            exc.project_uuid,
        )
