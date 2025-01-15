import logging

import sqlalchemy as sa

from aiohttp import web
from models_library.projects import ProjectID
from models_library.projects_nodes import Node, PartialNode
from models_library.projects_nodes_io import NodeID
from simcore_postgres_database.utils_repos import transaction_context
from simcore_postgres_database.webserver_models import projects_nodes
from sqlalchemy.ext.asyncio import AsyncConnection

from .exceptions import NodeNotFoundError
from ..db.plugin import get_asyncpg_engine

_logger = logging.getLogger(__name__)


_SELECTION_PROJECTS_NODES_DB_ARGS = [
    projects_nodes.c.key,
    projects_nodes.c.version,
    projects_nodes.c.label,
    projects_nodes.c.thumbnail,
    projects_nodes.c.inputs,
    projects_nodes.c.outputs,
]


async def get(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    project_id: ProjectID,
    node_id: NodeID,
) -> Node:
    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        get_stmt = sa.select(
            *_SELECTION_PROJECTS_NODES_DB_ARGS
        ).where(
            (projects_nodes.c.project_uuid == f"{project_id}")
            & (projects_nodes.c.node_id == f"{node_id}")
        )

        result = await conn.stream(get_stmt)
        assert result  # nosec

        row = await result.first()
        if row is None:
            raise NodeNotFoundError(
                project_uuid=f"{project_id}",
                node_uuid=f"{node_id}"
            )
        assert row  # nosec
        return Node.model_validate(row, from_attributes=True)


async def update(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    project_id: ProjectID,
    node_id: NodeID,
    partial_node: PartialNode,
) -> None:
    values = partial_node.model_dump(mode="json", exclude_unset=True)

    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        await conn.stream(
            projects_nodes.update()
            .values(**values)
            .where(
                (projects_nodes.c.project_uuid == f"{project_id}")
                & (projects_nodes.c.node_id == f"{node_id}")
            )
        )
