import datetime
import uuid
from dataclasses import asdict, dataclass, field

import psycopg2
from sqlalchemy import literal_column

from ._protocols import DBConnection
from .models.projects_nodes import projects_nodes
from .models.projects_to_projects_nodes import projects_to_projects_nodes


#
# Errors
#
class BaseProjectsNodesError(Exception):
    ...


class ProjectsNodesProjectNotFound(BaseProjectsNodesError):
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
        self, connection: DBConnection, *, node: ProjectsNodeCreate
    ) -> ProjectsNode:
        async with connection.begin():
            result = await connection.execute(
                projects_nodes.insert()
                .values(**asdict(node))
                .returning(literal_column("*"))
            )
            created_node = await result.first()
            assert created_node  # nosec
            created_node = ProjectsNode(**dict(created_node.items()))

            try:
                result = await connection.execute(
                    projects_to_projects_nodes.insert().values(
                        project_uuid=f"{self.project_uuid}",
                        node_id=f"{created_node.node_id}",
                    )
                )
                created_mapping = await result.one()
                assert created_mapping  # nosec
                return created_node
            except psycopg2.errors.ForeignKeyViolation as exc:
                raise ProjectsNodesProjectNotFound(
                    f"Project {self.project_uuid} not found"
                ) from exc

    async def list(self, connection: DBConnection) -> list[ProjectsNode]:
        ...

    async def get(
        self, connection: DBConnection, *, node_id: uuid.UUID
    ) -> ProjectsNode:
        ...

    async def update(
        self, connection: DBConnection, *, node_id: uuid.UUID, **values
    ) -> ProjectsNode:
        ...

    async def delete(self, connection: DBConnection, *, node_id: uuid.UUID) -> None:
        ...
