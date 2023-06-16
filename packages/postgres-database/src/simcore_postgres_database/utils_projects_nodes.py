import datetime
import uuid
from dataclasses import asdict, dataclass, field

import sqlalchemy
from aiopg.sa.connection import SAConnection
from sqlalchemy import literal_column

from .errors import ForeignKeyViolation, UniqueViolation
from .models.projects_nodes import projects_nodes
from .models.projects_to_projects_nodes import projects_to_projects_nodes


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
    required_resources: dict = field(default_factory=dict)


@dataclass(frozen=True, slots=True, kw_only=True)
class ProjectNode(ProjectNodeCreate):
    node_id: uuid.UUID
    created: datetime.datetime
    modified: datetime.datetime


@dataclass(frozen=True, slots=True, kw_only=True)
class ProjectNodesRepo:
    project_uuid: uuid.UUID

    async def add(
        self,
        connection: SAConnection,
        *,
        node_id: uuid.UUID,
        node: ProjectNodeCreate | None,
    ) -> ProjectNode:
        """creates a new entry in *projects_nodes* and *projects_to_projects_nodes* tables or
        attaches an existing one if node is set to `None`

        NOTE: Do not use this in an asyncio.gather call as this will fail!

        Raises:
            ProjectNodesProjectNotFound: in case the project_uuid does not exist
            ProjectNodesDuplicateNode: in case the node already exists
            ProjectsNodesNodeNotFound: in case the node does not exist

        """
        created_node = None
        async with connection.begin():
            try:
                if node:
                    result = await connection.execute(
                        projects_nodes.insert()
                        .values(node_id=f"{node_id}", **asdict(node))
                        .returning(literal_column("*"))
                    )
                    created_node_db = await result.first()
                    assert created_node_db  # nosec
                    created_node = ProjectNode(**dict(created_node_db.items()))
                else:
                    created_node = await self._get_node(connection, node_id=node_id)

                result = await connection.execute(
                    projects_to_projects_nodes.insert().values(
                        project_uuid=f"{self.project_uuid}",
                        node_id=f"{node_id}",
                    )
                )
                assert result.rowcount == 1  # nosec

                return created_node
            except ForeignKeyViolation as exc:
                # this happens when the project does not exist, as we first check the node exists
                raise ProjectNodesProjectNotFound(
                    f"Project {self.project_uuid} not found"
                ) from exc
            except UniqueViolation as exc:
                # this happens if the node already exists on creation
                raise ProjectNodesDuplicateNode(
                    f"Project node {node_id} already exists"
                ) from exc

    async def list(self, connection: SAConnection) -> list[ProjectNode]:
        """list the nodes in the current project

        NOTE: Do not use this in an asyncio.gather call as this will fail!
        """
        list_stmt = (
            sqlalchemy.select(projects_nodes)
            .select_from(self._join_projects_to_projects_nodes())
            .where(projects_to_projects_nodes.c.project_uuid == f"{self.project_uuid}")
        )
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

        get_stmt = (
            sqlalchemy.select(projects_nodes)
            .select_from(self._join_projects_to_projects_nodes())
            .where(
                (projects_to_projects_nodes.c.project_uuid == f"{self.project_uuid}")
                & (projects_to_projects_nodes.c.node_id == f"{node_id}")
            )
        )

        result = await connection.execute(get_stmt)
        assert result  # nosec
        row = await result.first()
        if row is None:
            raise ProjectNodesNodeNotFound(f"Node with {node_id} not found")
        assert row  # nosec
        return ProjectNode(**dict(row.items()))

    @staticmethod
    async def update(
        connection: SAConnection, *, node_id: uuid.UUID, **values
    ) -> ProjectNode:
        """update a node in the current project

        NOTE: Do not use this in an asyncio.gather call as this will fail!

        Raises:
            ProjectsNodesNodeNotFound: _description_
        """
        update_stmt = (
            projects_nodes.update()
            .values(**values)
            .where(projects_nodes.c.node_id == f"{node_id}")
            .returning(literal_column("*"))
        )
        result = await connection.execute(update_stmt)
        updated_entry = await result.first()
        if not updated_entry:
            raise ProjectNodesNodeNotFound(f"Node with {node_id} not found")
        assert updated_entry  # nosec
        return ProjectNode(**dict(updated_entry.items()))

    async def delete(self, connection: SAConnection, *, node_id: uuid.UUID) -> None:
        """delete a node in the current project (if the node is shared it will only unmap it)"""
        async with connection.begin():
            # remove mapping
            delete_stmt = sqlalchemy.delete(projects_to_projects_nodes).where(
                (projects_to_projects_nodes.c.node_id == f"{node_id}")
                & (projects_to_projects_nodes.c.project_uuid == f"{self.project_uuid}")
            )
            await connection.execute(delete_stmt)
            # if this was the last mapping then also delete the node itself
            num_remaining_mappings = await connection.scalar(
                sqlalchemy.select(sqlalchemy.func.count())
                .select_from(projects_to_projects_nodes)
                .where(projects_to_projects_nodes.c.node_id == f"{node_id}")
            )
            if num_remaining_mappings == 0:
                delete_stmt = sqlalchemy.delete(projects_nodes).where(
                    projects_nodes.c.node_id == f"{node_id}"
                )
                await connection.execute(delete_stmt)

    @staticmethod
    async def _get_node(connection: SAConnection, *, node_id: uuid.UUID) -> ProjectNode:
        get_stmt = sqlalchemy.select(projects_nodes).where(
            projects_nodes.c.node_id == f"{node_id}"
        )

        result = await connection.execute(get_stmt)
        assert result  # nosec
        row = await result.first()
        if row is None:
            raise ProjectNodesNodeNotFound(f"Node with {node_id} not found")
        assert row  # nosec
        return ProjectNode(**dict(row.items()))

    @staticmethod
    def _join_projects_to_projects_nodes():
        return projects_to_projects_nodes.join(
            projects_nodes,
            projects_to_projects_nodes.c.node_id == projects_nodes.c.node_id,
        )
