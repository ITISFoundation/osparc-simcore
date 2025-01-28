import logging

import sqlalchemy as sa
from aiohttp import web
from models_library.projects import ProjectID
from models_library.projects_nodes import Node, PartialNode
from models_library.projects_nodes_io import NodeID
from pydantic import TypeAdapter
from simcore_postgres_database.utils_repos import transaction_context
from simcore_postgres_database.webserver_models import projects_nodes
from sqlalchemy.ext.asyncio import AsyncConnection

from ..db.plugin import get_asyncpg_engine
from .exceptions import NodeNotFoundError

_logger = logging.getLogger(__name__)


_SELECTION_PROJECTS_NODES_DB_ARGS = [
    projects_nodes.c.key,
    projects_nodes.c.version,
    projects_nodes.c.label,
    projects_nodes.c.progress,
    projects_nodes.c.thumbnail,
    projects_nodes.c.input_access,
    projects_nodes.c.input_nodes,
    projects_nodes.c.inputs,
    projects_nodes.c.inputs_required,
    projects_nodes.c.inputs_units,
    projects_nodes.c.output_nodes,
    projects_nodes.c.outputs,
    projects_nodes.c.run_hash,
    projects_nodes.c.state,
    projects_nodes.c.parent,
    projects_nodes.c.boot_options,
]


async def get_node(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    project_id: ProjectID,
    node_id: NodeID,
) -> Node:
    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        get_stmt = sa.select(*_SELECTION_PROJECTS_NODES_DB_ARGS).where(
            (projects_nodes.c.project_uuid == f"{project_id}")
            & (projects_nodes.c.node_id == f"{node_id}")
        )

        result = await conn.stream(get_stmt)
        assert result  # nosec

        row = await result.first()
        if row is None:
            raise NodeNotFoundError(
                project_uuid=f"{project_id}", node_uuid=f"{node_id}"
            )
        assert row  # nosec
        return Node.model_validate(row, from_attributes=True)


async def list_nodes(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    project_id: ProjectID,
) -> list[Node]:
    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        result = await conn.stream(
            sa.select(*_SELECTION_PROJECTS_NODES_DB_ARGS).where(
                projects_nodes.c.project_uuid == f"{project_id}"
            )
        )
        rows = await result.all() or []
        return TypeAdapter(list[Node]).validate_python(rows)


async def update_node(
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
