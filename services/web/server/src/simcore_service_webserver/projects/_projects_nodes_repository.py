import logging
from typing import Any

import sqlalchemy as sa
from aiohttp import web
from models_library.projects import ProjectID
from models_library.projects_nodes import Node, PartialNode
from models_library.projects_nodes_io import NodeID
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
    projects_nodes.c.outputs,
    projects_nodes.c.run_hash,
    projects_nodes.c.state,
    projects_nodes.c.boot_options,
]

# Mapping from Node model alias (camelCase) to DB column name (snake_case)
_ALIAS_TO_COLUMN: dict[str, str] = {
    field_info.alias: field_name
    for field_name, field_info in Node.model_fields.items()
    if field_info.alias and field_info.alias != field_name
}


# Columns that actually exist in `projects_nodes` and are writable
_WRITABLE_COLUMNS: frozenset[str] = frozenset(c.name for c in projects_nodes.columns) - frozenset(
    {
        "created",
        "modified",
    }
)


def _node_dump_for_db(node_model: Node | PartialNode, *, exclude_unset: bool) -> dict[str, Any]:
    """Serializes a Node/PartialNode for DB storage.

    Uses by_alias=True so nested JSONB values (inputs, outputs, state)
    are serialized with camelCase keys (nodeUuid, currentStatus, etc.),
    then maps top-level keys from camelCase aliases back to snake_case DB columns.
    Filters out deprecated fields that have no corresponding column.
    """
    data = node_model.model_dump(mode="json", by_alias=True, exclude_unset=exclude_unset)
    mapped = {_ALIAS_TO_COLUMN.get(k, k): v for k, v in data.items()}
    return {k: v for k, v in mapped.items() if k in _WRITABLE_COLUMNS}


async def add(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    project_id: ProjectID,
    node_id: NodeID,
    node: Node,
    required_resources: dict[str, Any] | None = None,
) -> None:
    values = _node_dump_for_db(node, exclude_unset=True)
    if required_resources is not None:
        values["required_resources"] = required_resources

    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        await conn.execute(projects_nodes.insert().values(project_uuid=f"{project_id}", node_id=f"{node_id}", **values))


async def delete(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    project_id: ProjectID,
    node_id: NodeID,
) -> None:
    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        result = await conn.execute(
            projects_nodes.delete().where(
                (projects_nodes.c.project_uuid == f"{project_id}") & (projects_nodes.c.node_id == f"{node_id}")
            )
        )
        if result.rowcount == 0:
            raise NodeNotFoundError(project_uuid=f"{project_id}", node_uuid=f"{node_id}")


async def get(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    project_id: ProjectID,
    node_id: NodeID,
) -> Node:
    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        get_stmt = sa.select(*_SELECTION_PROJECTS_NODES_DB_ARGS).where(
            (projects_nodes.c.project_uuid == f"{project_id}") & (projects_nodes.c.node_id == f"{node_id}")
        )

        result = await conn.execute(get_stmt)
        assert result  # nosec

        row = result.one_or_none()
        if row is None:
            raise NodeNotFoundError(project_uuid=f"{project_id}", node_uuid=f"{node_id}")
        assert row  # nosec
        return Node.model_validate(row, from_attributes=True)


async def get_by_project(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    project_id: ProjectID,
) -> list[tuple[NodeID, Node]]:
    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        query = sa.select(*_SELECTION_PROJECTS_NODES_DB_ARGS).where(projects_nodes.c.project_uuid == f"{project_id}")

        stream = await conn.stream(query)
        assert stream  # nosec

        result: list[tuple[NodeID, Node]] = []
        async for row in stream:
            result.append((NodeID(row.node_id), Node.model_validate(row, from_attributes=True)))

        return result


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

        stream = await conn.stream(query)
        assert stream  # nosec

        projects_to_nodes: dict[ProjectID, list[tuple[NodeID, Node]]] = {pid: [] for pid in project_ids}

        async for row in stream:
            node = Node.model_validate(row, from_attributes=True)
            projects_to_nodes[ProjectID(row.project_uuid)].append((NodeID(row.node_id), node))

        return projects_to_nodes


async def update(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    project_id: ProjectID,
    node_id: NodeID,
    partial_node: PartialNode,
) -> Node:
    values = _node_dump_for_db(partial_node, exclude_unset=True)

    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        result = await conn.execute(
            projects_nodes.update()
            .values(**values)
            .where((projects_nodes.c.project_uuid == f"{project_id}") & (projects_nodes.c.node_id == f"{node_id}"))
            .returning(*_SELECTION_PROJECTS_NODES_DB_ARGS)
        )
        row = result.one_or_none()
        if row is None:
            raise NodeNotFoundError(project_uuid=f"{project_id}", node_uuid=f"{node_id}")
        return Node.model_validate(row, from_attributes=True)
