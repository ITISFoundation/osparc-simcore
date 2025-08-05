import datetime
import uuid
from dataclasses import dataclass
from typing import Annotated, Any

import asyncpg.exceptions  # type: ignore[import-untyped]
import sqlalchemy as sa
import sqlalchemy.exc
from common_library.async_tools import maybe_await
from common_library.basic_types import DEFAULT_FACTORY
from common_library.errors_classes import OsparcErrorMixin
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.sql.selectable import Subquery

from ._protocols import DBConnection
from .aiopg_errors import ForeignKeyViolation, UniqueViolation
from .models.projects import projects
from .models.projects_node_to_pricing_unit import projects_node_to_pricing_unit
from .models.projects_nodes import projects_nodes
from .utils_aiosqlalchemy import map_db_exception


#
# Errors
#
class BaseProjectNodesError(OsparcErrorMixin, RuntimeError):
    msg_template: str = "Project nodes unexpected error"


class ProjectNodesProjectNotFoundError(BaseProjectNodesError):
    msg_template: str = "Project {project_uuid} not found"


class ProjectNodesNodeNotFoundError(BaseProjectNodesError):
    msg_template: str = "Node {node_id!r} from project {project_uuid!r} not found"


class ProjectNodesNonUniqueNodeFoundError(BaseProjectNodesError):
    msg_template: str = (
        "Multiple project found containing node {node_id}. TIP: misuse, the same node ID was found in several projects."
    )


class ProjectNodesDuplicateNodeError(BaseProjectNodesError):
    msg_template: str = (
        "Project node already exists, you cannot have 2x the same node in the same project."
    )


class ProjectNodeCreate(BaseModel):
    node_id: uuid.UUID
    required_resources: Annotated[dict[str, Any], Field(default_factory=dict)] = (
        DEFAULT_FACTORY
    )
    key: str
    version: str
    label: str
    progress: float | None = None
    thumbnail: str | None = None
    input_access: dict[str, Any] | None = None
    input_nodes: list[str] | None = None
    inputs: dict[str, Any] | None = None
    inputs_units: dict[str, Any] | None = None
    output_nodes: list[str] | None = None
    outputs: dict[str, Any] | None = None
    run_hash: str | None = None
    state: dict[str, Any] | None = None
    parent: str | None = None
    boot_options: dict[str, Any] | None = None

    @classmethod
    def get_field_names(cls, *, exclude: set[str]) -> set[str]:
        return cls.model_fields.keys() - exclude

    def model_dump_as_node(self) -> dict[str, Any]:
        """Converts a ProjectNode from the database to a Node model for the API.

        Handles field mapping and excludes database-specific fields that are not
        part of the Node model.
        """
        # Get all ProjectNode fields except those that don't belong in Node
        exclude_fields = {"node_id", "required_resources"}
        return self.model_dump(
            # NOTE: this setup ensures using the defaults provided in Node model when the db does not
            # provide them, e.g. `state`
            exclude=exclude_fields,
            exclude_none=True,
            exclude_unset=True,
        )

    model_config = ConfigDict(frozen=True)


class ProjectNode(ProjectNodeCreate):
    created: datetime.datetime
    modified: datetime.datetime

    model_config = ConfigDict(from_attributes=True)

    def model_dump_as_node(self) -> dict[str, Any]:
        """Converts a ProjectNode from the database to a Node model for the API.

        Handles field mapping and excludes database-specific fields that are not
        part of the Node model.
        """
        # Get all ProjectNode fields except those that don't belong in Node
        exclude_fields = {"node_id", "required_resources", "created", "modified"}
        return self.model_dump(
            # NOTE: this setup ensures using the defaults provided in Node model when the db does not
            # provide them, e.g. `state`
            exclude=exclude_fields,
            exclude_none=True,
            exclude_unset=True,
        )


def make_workbench_subquery() -> Subquery:
    return (
        sa.select(
            projects_nodes.c.project_uuid,
            sa.func.json_object_agg(
                projects_nodes.c.node_id,
                sa.func.json_build_object(
                    "key",
                    projects_nodes.c.key,
                    "version",
                    projects_nodes.c.version,
                    "label",
                    projects_nodes.c.label,
                    "progress",
                    projects_nodes.c.progress,
                    "thumbnail",
                    projects_nodes.c.thumbnail,
                    "inputAccess",
                    projects_nodes.c.input_access,
                    "inputNodes",
                    projects_nodes.c.input_nodes,
                    "inputs",
                    projects_nodes.c.inputs,
                    "inputsRequired",
                    projects_nodes.c.inputs_required,
                    "inputsUnits",
                    projects_nodes.c.inputs_units,
                    "outputNodes",
                    projects_nodes.c.output_nodes,
                    "outputs",
                    projects_nodes.c.outputs,
                    "runHash",
                    projects_nodes.c.run_hash,
                    "state",
                    projects_nodes.c.state,
                    "parent",
                    projects_nodes.c.parent,
                    "bootOptions",
                    projects_nodes.c.boot_options,
                ),
            ).label("workbench"),
        )
        .select_from(
            projects_nodes.join(
                projects, projects_nodes.c.project_uuid == projects.c.uuid
            )
        )
        .group_by(projects_nodes.c.project_uuid)
        .subquery()
    )


@dataclass(frozen=True, kw_only=True)
class ProjectNodesRepo:
    project_uuid: uuid.UUID

    async def add(
        self,
        connection: DBConnection,
        *,
        nodes: list[ProjectNodeCreate],
    ) -> list[ProjectNode]:
        """Creates a new entry in *projects_nodes* table

        NOTE: Do not use this in an asyncio.gather call as this will fail!

        Raises:
            ProjectNodesProjectNotFound: in case the project_uuid does not exist
            ProjectNodesDuplicateNode: in case the node already exists
            ProjectsNodesNodeNotFound: in case the node does not exist

        """
        if not nodes:
            return []

        values = [
            {
                "project_uuid": f"{self.project_uuid}",
                **node.model_dump(mode="json"),
            }
            for node in nodes
        ]

        insert_stmt = (
            projects_nodes.insert()
            .values(values)
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
            rows = await maybe_await(result.fetchall())
            assert isinstance(rows, list)  # nosec
            return [ProjectNode.model_validate(r) for r in rows]

        except ForeignKeyViolation as exc:
            # this happens when the project does not exist, as we first check the node exists
            raise ProjectNodesProjectNotFoundError(
                project_uuid=self.project_uuid
            ) from exc

        except UniqueViolation as exc:
            # this happens if the node already exists on creation
            raise ProjectNodesDuplicateNodeError from exc

        except sqlalchemy.exc.IntegrityError as exc:
            raise map_db_exception(
                exc,
                {
                    asyncpg.exceptions.UniqueViolationError.sqlstate: (
                        ProjectNodesDuplicateNodeError,
                        {"project_uuid": self.project_uuid},
                    ),
                    asyncpg.exceptions.ForeignKeyViolationError.sqlstate: (
                        ProjectNodesProjectNotFoundError,
                        {"project_uuid": self.project_uuid},
                    ),
                },
            ) from exc

    async def list(self, connection: DBConnection) -> list[ProjectNode]:
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
        rows = await maybe_await(result.fetchall())
        assert isinstance(rows, list)  # nosec
        return [ProjectNode.model_validate(row) for row in rows]

    async def get(self, connection: DBConnection, *, node_id: uuid.UUID) -> ProjectNode:
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
        row = await maybe_await(result.first())
        if row is None:
            raise ProjectNodesNodeNotFoundError(
                project_uuid=self.project_uuid, node_id=node_id
            )
        assert row  # nosec
        return ProjectNode.model_validate(row)

    async def update(
        self, connection: DBConnection, *, node_id: uuid.UUID, **values
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
        row = await maybe_await(result.first())
        if not row:
            raise ProjectNodesNodeNotFoundError(
                project_uuid=self.project_uuid, node_id=node_id
            )
        assert row  # nosec
        return ProjectNode.model_validate(row)

    async def delete(self, connection: DBConnection, *, node_id: uuid.UUID) -> None:
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
        self, connection: DBConnection, *, node_uuid: uuid.UUID
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
        row = await maybe_await(result.fetchone())
        if row is not None:
            return (row.pricing_plan_id, row.pricing_unit_id)  # type: ignore[union-attr]
        return None

    async def connect_pricing_unit_to_project_node(
        self,
        connection: DBConnection,
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

    @staticmethod
    async def get_project_id_from_node_id(
        connection: DBConnection, *, node_id: uuid.UUID
    ) -> uuid.UUID:
        """
        WARNING: this function should not be used! it has a flaw! a Node ID is not unique and there can
        be more than one project linked to it.

        Raises:
            ProjectNodesNodeNotFound: if no node_id found
            ProjectNodesNonUniqueNodeFoundError: there are multiple projects that contain that node
        """
        get_stmt = sqlalchemy.select(projects_nodes.c.project_uuid).where(
            projects_nodes.c.node_id == f"{node_id}"
        )
        result = await connection.execute(get_stmt)
        project_ids = await maybe_await(result.fetchall())
        assert isinstance(project_ids, list)  # nosec
        if not project_ids:
            raise ProjectNodesNodeNotFoundError(project_uuid=None, node_id=node_id)
        if len(project_ids) > 1:
            raise ProjectNodesNonUniqueNodeFoundError(node_id=node_id)
        return uuid.UUID(project_ids[0].project_uuid)
