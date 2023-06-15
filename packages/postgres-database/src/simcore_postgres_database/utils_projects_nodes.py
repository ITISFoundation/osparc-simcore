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
class BaseProjectsNodesError(Exception):
    ...


class ProjectsNodesProjectNotFound(BaseProjectsNodesError):
    ...


class ProjectsNodesNodeNotFound(BaseProjectsNodesError):
    ...


class ProjectsNodesOperationNotAllowed(BaseProjectsNodesError):
    ...


class ProjectsNodesDuplicateNode(BaseProjectsNodesError):
    ...


@dataclass(frozen=True, slots=True, kw_only=True)
class ProjectsNodeCreate:
    node_id: uuid.UUID
    required_resources: dict = field(default_factory=dict)


@dataclass(frozen=True, slots=True, kw_only=True)
class ProjectsNode(ProjectsNodeCreate):
    created: datetime.datetime
    modified: datetime.datetime


@dataclass(frozen=True, slots=True, kw_only=True)
class ProjectsNodesRepo:
    project_uuid: uuid.UUID

    async def create(
        self, connection: SAConnection, *, node: ProjectsNodeCreate
    ) -> ProjectsNode:
        """creates a new entry in *projects_noeds* and *projects_to_projects_nodes* tables

        NOTE: Do not use this in an asyncio.gather call as this will fail!

        Raises:
            ProjectsNodesProjectNotFound: in case the project_uuid does not exist
            ProjectsNodesDuplicateNode: in case the node already exists

        """
        async with connection.begin():
            try:
                result = await connection.execute(
                    projects_nodes.insert()
                    .values(**asdict(node))
                    .returning(literal_column("*"))
                )
                created_node = await result.first()
                assert created_node  # nosec
                created_node = ProjectsNode(**dict(created_node.items()))

                result = await connection.execute(
                    projects_to_projects_nodes.insert().values(
                        project_uuid=f"{self.project_uuid}",
                        node_id=f"{created_node.node_id}",
                    )
                )
                assert result.rowcount == 1  # nosec
                return created_node
            except ForeignKeyViolation as exc:
                # this happens when the project does not exist
                raise ProjectsNodesProjectNotFound(
                    f"Project {self.project_uuid} not found"
                ) from exc
            except UniqueViolation as exc:
                # this happens if the node already exists
                raise ProjectsNodesDuplicateNode(
                    f"Project node {node.node_id} already exists"
                ) from exc

    async def add(
        self, connection: SAConnection, *, node_id: uuid.UUID
    ) -> ProjectsNode:
        try:
            result = await connection.execute(
                projects_to_projects_nodes.insert().values(
                    project_uuid=f"{self.project_uuid}",
                    node_id=f"{node_id}",
                )
            )
            assert result.rowcount == 1  # nosec

            return await self.get(connection, node_id=node_id)

        except ForeignKeyViolation as exc:
            raise ProjectsNodesOperationNotAllowed(
                f"Node {node_id=} cannot be added to project {self.project_uuid}"
            ) from exc

    async def list(self, connection: SAConnection) -> list[ProjectsNode]:
        list_stmt = (
            sqlalchemy.select(projects_nodes)
            .select_from(self._join_projects_to_projects_nodes())
            .where(projects_to_projects_nodes.c.project_uuid == f"{self.project_uuid}")
        )
        nodes = [
            ProjectsNode(**dict(row.items()))
            async for row in connection.execute(list_stmt)
        ]
        return nodes

    async def get(
        self, connection: SAConnection, *, node_id: uuid.UUID
    ) -> ProjectsNode:
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
            raise ProjectsNodesNodeNotFound(f"node with {node_id} not found")
        assert row  # nosec
        return ProjectsNode(**dict(row.items()))

    async def update(
        self, connection: SAConnection, *, node_id: uuid.UUID, **values
    ) -> ProjectsNode:
        ...

    async def delete(self, connection: SAConnection, *, node_id: uuid.UUID) -> None:
        delete_stmt = sqlalchemy.delete(projects_to_projects_nodes).where(
            (projects_to_projects_nodes.c.node_id == f"{node_id}")
            & (projects_to_projects_nodes.c.project_uuid == f"{self.project_uuid}")
        )
        await connection.execute(delete_stmt)

    @staticmethod
    def _join_projects_to_projects_nodes():
        return projects_to_projects_nodes.join(
            projects_nodes,
            projects_to_projects_nodes.c.node_id == projects_nodes.c.node_id,
        )
