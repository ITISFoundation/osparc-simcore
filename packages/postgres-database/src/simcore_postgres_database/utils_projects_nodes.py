import datetime
import uuid
from dataclasses import asdict, dataclass, field

import sqlalchemy
from aiopg.sa.connection import SAConnection

from .errors import ForeignKeyViolation, UniqueViolation
from .models.projects_nodes import projects_nodes


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
    required_resources: dict = field(default_factory=dict)


@dataclass(frozen=True, slots=True, kw_only=True)
class ProjectNode(ProjectNodeCreate):
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
        insertable_values = [
            {
                "project_uuid": f"{self.project_uuid}",
                **asdict(node),
            }
            for node in nodes
        ]
        try:
            result = await connection.execute(
                projects_nodes.insert()
                .values(insertable_values)
                .returning(
                    *[
                        c
                        for c in projects_nodes.c
                        if c is not projects_nodes.c.project_uuid
                    ]
                )
            )
            created_nodes_db = await result.fetchall()
            assert created_nodes_db  # nosec
            created_nodes = [
                ProjectNode(**dict(created_node_db.items()))
                for created_node_db in created_nodes_db
            ]

            return created_nodes
        except ForeignKeyViolation as exc:
            # this happens when the project does not exist, as we first check the node exists
            raise ProjectNodesProjectNotFound(
                f"Project {self.project_uuid} not found"
            ) from exc
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
            *[c for c in projects_nodes.c if c is not projects_nodes.c.project_uuid]
        ).where(projects_nodes.c.project_uuid == f"{self.project_uuid}")
        nodes = [
            ProjectNode(**dict(row.items()))
            async for row in connection.execute(list_stmt)
        ]
        return nodes

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
            raise ProjectNodesNodeNotFound(f"Node with {node_id} not found")
        assert row  # nosec
        return ProjectNode(**dict(row.items()))

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
        updated_entry = await result.first()
        if not updated_entry:
            raise ProjectNodesNodeNotFound(f"Node with {node_id} not found")
        assert updated_entry  # nosec
        return ProjectNode(**dict(updated_entry.items()))

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
