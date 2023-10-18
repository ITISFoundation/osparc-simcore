import datetime
import uuid
from dataclasses import asdict, dataclass, field, fields
from typing import Any

import sqlalchemy
from aiopg.sa.connection import SAConnection
from simcore_postgres_database.models.projects_node_to_pricing_unit import (
    projects_node_to_pricing_unit,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert

from .errors import ForeignKeyViolation, UniqueViolation
from .models.projects_nodes import projects_nodes
from .utils_models import FromRowMixin


#
# Errors
#
class BaseProjectNodesError(Exception):
    ...


class ProjectNodesProjectNotFound(BaseProjectNodesError):
    ...


class ProjectNodesNodeNotFound(BaseProjectNodesError):
    ...


class ProjectNodesOperationNotAllowed(BaseProjectNodesError):
    ...


class ProjectNodesDuplicateNode(BaseProjectNodesError):
    ...


@dataclass(frozen=True, slots=True, kw_only=True)
class ProjectNodeCreate:
    node_id: uuid.UUID
    required_resources: dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def get_field_names(*, exclude: set[str]) -> set[str]:
        return {f.name for f in fields(ProjectNodeCreate) if f.name not in exclude}


@dataclass(frozen=True, slots=True, kw_only=True)
class ProjectNode(ProjectNodeCreate, FromRowMixin):
    created: datetime.datetime
    modified: datetime.datetime


@dataclass(frozen=True, slots=True, kw_only=True)
class ProjectNodesRepo:
    project_uuid: uuid.UUID

    async def add(
        self,
        connection: SAConnection,
        *,
        nodes: list[ProjectNodeCreate],
    ) -> list[ProjectNode]:
        """creates a new entry in *projects_nodes* and *projects_to_projects_nodes* tables

        NOTE: Do not use this in an asyncio.gather call as this will fail!

        Raises:
            ProjectNodesProjectNotFound: in case the project_uuid does not exist
            ProjectNodesDuplicateNode: in case the node already exists
            ProjectsNodesNodeNotFound: in case the node does not exist

        """
        if not nodes:
            return []
        insert_stmt = (
            projects_nodes.insert()
            .values(
                [
                    {
                        "project_uuid": f"{self.project_uuid}",
                        **asdict(node),
                    }
                    for node in nodes
                ]
            )
            .returning(
                *[
                    c
                    for c in projects_nodes.columns
                    if c is not projects_nodes.c.project_uuid
                ]
            )
        )

        try:
            result = await connection.execute(insert_stmt)
            assert result  # nosec
            rows = await result.fetchall()
            assert rows is not None  # nosec
            return [ProjectNode.from_row(r) for r in rows]
        except ForeignKeyViolation as exc:
            # this happens when the project does not exist, as we first check the node exists
            msg = f"Project {self.project_uuid} not found"
            raise ProjectNodesProjectNotFound(msg) from exc
        except UniqueViolation as exc:
            # this happens if the node already exists on creation
            raise ProjectNodesDuplicateNode(
                f"Project node already exists: {exc}"
            ) from exc

    async def list(self, connection: SAConnection) -> list[ProjectNode]:
        """list the nodes in the current project

        NOTE: Do not use this in an asyncio.gather call as this will fail!
        """
        list_stmt = sqlalchemy.select(
            *[
                c
                for c in projects_nodes.columns
                if c is not projects_nodes.c.project_uuid
            ]
        ).where(projects_nodes.c.project_uuid == f"{self.project_uuid}")
        result = await connection.execute(list_stmt)
        assert result  # nosec
        rows = await result.fetchall()
        assert rows is not None  # nosec
        return [ProjectNode.from_row(row) for row in rows]

    async def get(self, connection: SAConnection, *, node_id: uuid.UUID) -> ProjectNode:
        """get a node in the current project

        NOTE: Do not use this in an asyncio.gather call as this will fail!

        Raises:
            ProjectsNodesNodeNotFound: _description_
        """

        get_stmt = sqlalchemy.select(
            *[c for c in projects_nodes.c if c is not projects_nodes.c.project_uuid]
        ).where(
            (projects_nodes.c.project_uuid == f"{self.project_uuid}")
            & (projects_nodes.c.node_id == f"{node_id}")
        )

        result = await connection.execute(get_stmt)
        assert result  # nosec
        row = await result.first()
        if row is None:
            msg = f"Node with {node_id} not found"
            raise ProjectNodesNodeNotFound(msg)
        assert row  # nosec
        return ProjectNode.from_row(row)

    async def update(
        self, connection: SAConnection, *, node_id: uuid.UUID, **values
    ) -> ProjectNode:
        """update a node in the current project

        NOTE: Do not use this in an asyncio.gather call as this will fail!

        Raises:
            ProjectsNodesNodeNotFound: _description_
        """
        update_stmt = (
            projects_nodes.update()
            .values(**values)
            .where(
                (projects_nodes.c.project_uuid == f"{self.project_uuid}")
                & (projects_nodes.c.node_id == f"{node_id}")
            )
            .returning(
                *[c for c in projects_nodes.c if c is not projects_nodes.c.project_uuid]
            )
        )
        result = await connection.execute(update_stmt)
        row = await result.first()
        if not row:
            msg = f"Node with {node_id} not found"
            raise ProjectNodesNodeNotFound(msg)
        assert row  # nosec
        return ProjectNode.from_row(row)

    async def delete(self, connection: SAConnection, *, node_id: uuid.UUID) -> None:
        """delete a node in the current project

        NOTE: Do not use this in an asyncio.gather call as this will fail!

        Raises:
            Nothing special
        """
        delete_stmt = sqlalchemy.delete(projects_nodes).where(
            (projects_nodes.c.project_uuid == f"{self.project_uuid}")
            & (projects_nodes.c.node_id == f"{node_id}")
        )
        await connection.execute(delete_stmt)

    async def get_project_node_pricing_unit_id(
        self, connection: SAConnection, *, node_uuid: uuid.UUID
    ) -> tuple | None:
        """get a pricing unit that is connected to the project node or None if there is non connected

        NOTE: Do not use this in an asyncio.gather call as this will fail!
        """
        result = await connection.execute(
            sqlalchemy.select(
                projects_node_to_pricing_unit.c.pricing_plan_id,
                projects_node_to_pricing_unit.c.pricing_unit_id,
            )
            .select_from(
                projects_nodes.join(
                    projects_node_to_pricing_unit,
                    projects_nodes.c.project_node_id
                    == projects_node_to_pricing_unit.c.project_node_id,
                )
            )
            .where(
                (projects_nodes.c.project_uuid == f"{self.project_uuid}")
                & (projects_nodes.c.node_id == f"{node_uuid}")
            )
        )
        row = await result.fetchone()
        if row:
            return (row[0], row[1])
        return None

    async def connect_pricing_unit_to_project_node(
        self,
        connection: SAConnection,
        *,
        node_uuid: uuid.UUID,
        pricing_plan_id: int,
        pricing_unit_id: int,
    ) -> None:
        result = await connection.scalar(
            sqlalchemy.select(projects_nodes.c.project_node_id).where(
                (projects_nodes.c.project_uuid == f"{self.project_uuid}")
                & (projects_nodes.c.node_id == f"{node_uuid}")
            )
        )
        project_node_id = int(result) if result else 0

        insert_stmt = pg_insert(projects_node_to_pricing_unit).values(
            project_node_id=project_node_id,
            pricing_plan_id=pricing_plan_id,
            pricing_unit_id=pricing_unit_id,
            created=sqlalchemy.func.now(),
            modified=sqlalchemy.func.now(),
        )
        on_update_stmt = insert_stmt.on_conflict_do_update(
            index_elements=[
                projects_node_to_pricing_unit.c.project_node_id,
            ],
            set_={
                "pricing_plan_id": insert_stmt.excluded.pricing_plan_id,
                "pricing_unit_id": insert_stmt.excluded.pricing_unit_id,
                "modified": sqlalchemy.func.now(),
            },
        )
        await connection.execute(on_update_stmt)
