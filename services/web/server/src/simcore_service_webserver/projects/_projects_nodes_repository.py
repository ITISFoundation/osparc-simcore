import logging

import sqlalchemy as sa
from aiohttp import web
from models_library.projects import ProjectID
from models_library.projects_nodes import PartialNode
from models_library.projects_nodes_io import NodeID
from simcore_postgres_database.utils_repos import transaction_context
from simcore_postgres_database.webserver_models import projects_nodes
from sqlalchemy.ext.asyncio import AsyncConnection

from ..db.plugin import get_asyncpg_engine
from .models import NodeDB

_logger = logging.getLogger(__name__)


async def update(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    project_id: ProjectID,
    node_id: NodeID,
    node: PartialNode,
) -> None:
    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        await conn.stream(
            projects_nodes.update()
            .values(**NodeDB.model_construct(**node.model_dump()).model_dump(mode="json", exclude_defaults=True, exclude_unset=True, exclude_none=True))
            .where(
                sa.and_(
                    projects_nodes.c.project_uuid == f"{project_id}",
                    projects_nodes.c.node_id == f"{node_id}",
                )
            )
        )
