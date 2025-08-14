import logging

import sqlalchemy as sa
from aiohttp import web
from models_library.projects import ProjectID
from models_library.projects_nodes import Node, PartialNode
from models_library.projects_nodes_io import NodeID
from simcore_postgres_database.utils_projects_nodes import ProjectNode
from simcore_postgres_database.utils_repos import (
    pass_or_acquire_connection,
    transaction_context,
)
from simcore_postgres_database.webserver_models import projects_nodes
from sqlalchemy.ext.asyncio import AsyncConnection

from ..db.plugin import get_asyncpg_engine
from .exceptions import NodeNotFoundError

_logger = logging.getLogger(__name__)


_SELECTION_PROJECTS_NODES_DB_ARGS = [
    projects_nodes.c.node_id,
    projects_nodes.c.project_uuid,
    projects_nodes.c.key,
    projects_nodes.c.version,
    projects_nodes.c.label,
    projects_nodes.c.created,
    projects_nodes.c.modified,
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


async def add(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    project_id: ProjectID,
    node_id: NodeID,
    node: Node,
) -> None:
    values = node.model_dump(mode="json", exclude_none=True)

    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        await conn.execute(
            projects_nodes.insert().values(
                project_uuid=f"{project_id}", node_id=f"{node_id}", **values
            )
        )


async def delete(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    project_id: ProjectID,
    node_id: NodeID,
) -> None:
    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        await conn.execute(
            projects_nodes.delete().where(
                (projects_nodes.c.project_uuid == f"{project_id}")
                & (projects_nodes.c.node_id == f"{node_id}")
            )
        )


async def get(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    project_id: ProjectID,
    node_id: NodeID,
) -> Node:
    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        query = sa.select(*_SELECTION_PROJECTS_NODES_DB_ARGS).where(
            (projects_nodes.c.project_uuid == f"{project_id}")
            & (projects_nodes.c.node_id == f"{node_id}")
        )

        result = await conn.stream(query)
        assert result  # nosec

        row = await result.first()
        if row is None:
            raise NodeNotFoundError(
                project_uuid=f"{project_id}", node_uuid=f"{node_id}"
            )
        assert row  # nosec
        return Node.model_validate(row, from_attributes=True)


async def get_by_project(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    project_id: ProjectID,
) -> list[tuple[NodeID, Node]]:
    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        query = sa.select(*_SELECTION_PROJECTS_NODES_DB_ARGS).where(
            projects_nodes.c.project_uuid == f"{project_id}"
        )

        result = await conn.stream(query)
        assert result  # nosec

        rows = await result.all()
        return [
            (
                NodeID(row.node_id),
                Node.model_validate(
                    ProjectNode.model_validate(row, from_attributes=True).model_dump(
                        exclude_none=True,
                        exclude_unset=True,
                        exclude={"node_id", "created", "modified"},
                    )
                ),
            )
            for row in rows
        ]


async def get_by_projects(
    app: web.Application,
    project_ids: set[ProjectID],
    connection: AsyncConnection | None = None,
) -> dict[ProjectID, list[tuple[NodeID, Node]]]:
    if not project_ids:
        return {}

    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        query = sa.select(*_SELECTION_PROJECTS_NODES_DB_ARGS).where(
            projects_nodes.c.project_uuid.in_([f"{pid}" for pid in project_ids])
        )

        result = await conn.stream(query)
        assert result  # nosec

        rows = await result.all()

        # Initialize dict with empty lists for all requested project_ids
        projects_to_nodes: dict[ProjectID, list[tuple[NodeID, Node]]] = {
            pid: [] for pid in project_ids
        }

        # Fill in the actual data
        for row in rows:
            node = Node.model_validate(
                ProjectNode.model_validate(row).model_dump(
                    exclude_none=True,
                    exclude_unset=True,
                    exclude={"node_id", "created", "modified"},
                )
            )

            projects_to_nodes[ProjectID(row.project_uuid)].append(
                (NodeID(row.node_id), node)
            )

        return projects_to_nodes


async def update(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    project_id: ProjectID,
    node_id: NodeID,
    partial_node: PartialNode,
) -> Node:
    values = partial_node.model_dump(mode="json", exclude_unset=True)

    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        result = await conn.stream(
            projects_nodes.update()
            .values(**values)
            .where(
                (projects_nodes.c.project_uuid == f"{project_id}")
                & (projects_nodes.c.node_id == f"{node_id}")
            )
            .returning(*_SELECTION_PROJECTS_NODES_DB_ARGS)
        )
        return Node.model_validate(await result.first(), from_attributes=True)
