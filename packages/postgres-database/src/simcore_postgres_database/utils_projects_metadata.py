import datetime
import uuid
from typing import Any

import sqlalchemy as sa
from aiopg.sa.connection import SAConnection
from aiopg.sa.result import ResultProxy, RowProxy
from common_library.errors_classes import OsparcErrorMixin
from pydantic import BaseModel, ConfigDict
from sqlalchemy.dialects.postgresql import insert as pg_insert

from .errors import ForeignKeyViolation
from .models.projects import projects
from .models.projects_metadata import projects_metadata

#
# Errors
#


class BaseProjectsMetadataError(OsparcErrorMixin, RuntimeError):
    msg_template: str = "Project metadata unexpected error"


class DBProjectNotFoundError(BaseProjectsMetadataError):
    msg_template: str = "Project project_uuid={project_uuid!r} not found"


class DBProjectInvalidAncestorsError(BaseProjectsMetadataError):
    msg_template: str = (
        "Projects metadata invalid ancestors given (both must be set or none)"
    )


class DBProjectInvalidParentProjectError(BaseProjectsMetadataError):
    msg_template: str = "Project project_uuid={project_uuid!r} has invalid parent project uuid={parent_project_uuid!r}"


class DBProjectInvalidParentNodeError(BaseProjectsMetadataError):
    msg_template: str = "Project project_uuid={project_uuid!r} has invalid parent project uuid={parent_node_id!r}"


#
# Data
#


class ProjectMetadata(BaseModel):
    custom: dict[str, Any] | None
    created: datetime.datetime | None
    modified: datetime.datetime | None
    parent_project_uuid: uuid.UUID | None
    parent_node_id: uuid.UUID | None
    root_parent_project_uuid: uuid.UUID | None
    root_parent_node_id: uuid.UUID | None
    model_config = ConfigDict(frozen=True, from_attributes=True)


#
# Helpers
#


async def get(connection: SAConnection, project_uuid: uuid.UUID) -> ProjectMetadata:
    """
    Raises:
        DBProjectNotFoundError: project not found

    """
    # JOIN LEFT OUTER
    get_stmt = (
        sa.select(
            projects.c.uuid,
            projects_metadata.c.custom,
            projects_metadata.c.created,
            projects_metadata.c.modified,
            projects_metadata.c.parent_project_uuid,
            projects_metadata.c.parent_node_id,
            projects_metadata.c.root_parent_project_uuid,
            projects_metadata.c.root_parent_node_id,
        )
        .select_from(
            sa.join(
                projects,
                projects_metadata,
                projects.c.uuid == projects_metadata.c.project_uuid,
                isouter=True,
            )
        )
        .where(projects.c.uuid == f"{project_uuid}")
    )
    result: ResultProxy = await connection.execute(get_stmt)
    row: RowProxy | None = await result.first()
    if row is None:
        raise DBProjectNotFoundError(project_uuid=project_uuid)
    return ProjectMetadata.model_validate(row)


def _check_valid_ancestors_combination(
    project_uuid: uuid.UUID,
    parent_project_uuid: uuid.UUID | None,
    parent_node_id: uuid.UUID | None,
) -> None:
    if project_uuid == parent_project_uuid:
        raise DBProjectInvalidAncestorsError
    if parent_project_uuid is not None and parent_node_id is None:
        raise DBProjectInvalidAncestorsError
    if parent_project_uuid is None and parent_node_id is not None:
        raise DBProjectInvalidAncestorsError


async def _project_has_any_child(
    connection: SAConnection, project_uuid: uuid.UUID
) -> bool:
    get_stmt = sa.select(projects_metadata.c.project_uuid).where(
        projects_metadata.c.parent_project_uuid == f"{project_uuid}"
    )
    if await connection.scalar(get_stmt) is not None:
        return True
    return False


async def _compute_root_parent_from_parent(
    connection: SAConnection,
    *,
    project_uuid: uuid.UUID,
    parent_project_uuid: uuid.UUID | None,
    parent_node_id: uuid.UUID | None,
) -> tuple[uuid.UUID | None, uuid.UUID | None]:
    if parent_project_uuid is None and parent_node_id is None:
        return None, None

    try:
        assert parent_project_uuid is not None  # nosec
        parent_project_metadata = await get(connection, parent_project_uuid)
        if parent_project_metadata.root_parent_project_uuid is not None:
            assert parent_project_metadata.root_parent_node_id is not None  # nosec
            return (
                parent_project_metadata.root_parent_project_uuid,
                parent_project_metadata.root_parent_node_id,
            )
        # that means this is the root already
        return parent_project_uuid, parent_node_id
    except DBProjectNotFoundError as err:
        raise DBProjectInvalidParentProjectError(
            project_uuid=project_uuid, parent_project_uuid=parent_project_uuid
        ) from err


async def set_project_ancestors(
    connection: SAConnection,
    *,
    project_uuid: uuid.UUID,
    parent_project_uuid: uuid.UUID | None,
    parent_node_id: uuid.UUID | None,
) -> ProjectMetadata:
    """
    Raises:
        NotImplementedError: if you touch ancestry of a project that has children
        DBProjectInvalidAncestorsError: if you pass invalid parents
        DBProjectInvalidParentProjectError: the parent_project_uuid is invalid
        DBProjectInvalidParentNodeError: the parent_node_ID is invalid
        DBProjectNotFoundError: the project_uuid is not found
    """
    _check_valid_ancestors_combination(
        project_uuid, parent_project_uuid, parent_node_id
    )
    if await _project_has_any_child(connection, project_uuid):
        msg = "Cannot set ancestors for a project with children"
        raise NotImplementedError(msg)
    (
        root_parent_project_uuid,
        root_parent_node_id,
    ) = await _compute_root_parent_from_parent(
        connection,
        project_uuid=project_uuid,
        parent_project_uuid=parent_project_uuid,
        parent_node_id=parent_node_id,
    )
    data = {
        "project_uuid": f"{project_uuid}",
        "parent_project_uuid": (
            f"{parent_project_uuid}" if parent_project_uuid is not None else None
        ),
        "parent_node_id": f"{parent_node_id}" if parent_node_id is not None else None,
        "root_parent_project_uuid": (
            f"{root_parent_project_uuid}"
            if root_parent_project_uuid is not None
            else None
        ),
        "root_parent_node_id": (
            f"{root_parent_node_id}" if root_parent_node_id is not None else None
        ),
    }
    insert_stmt = pg_insert(projects_metadata).values(**data)
    upsert_stmt = insert_stmt.on_conflict_do_update(
        index_elements=[projects_metadata.c.project_uuid],
        set_=data,
    ).returning(sa.literal_column("*"))

    try:
        result: ResultProxy = await connection.execute(upsert_stmt)
        row: RowProxy | None = await result.first()
        assert row  # nosec
        return ProjectMetadata.model_validate(row)

    except ForeignKeyViolation as err:
        assert err.pgerror is not None  # nosec  # noqa: PT017
        if "fk_projects_metadata_parent_node_id" in err.pgerror:
            raise DBProjectInvalidParentNodeError(
                project_uuid=project_uuid, parent_node_id=parent_node_id
            ) from err

        raise DBProjectNotFoundError(project_uuid=project_uuid) from err


async def set_project_custom_metadata(
    connection: SAConnection,
    *,
    project_uuid: uuid.UUID,
    custom_metadata: dict[str, Any],
) -> ProjectMetadata:
    data = {
        "project_uuid": f"{project_uuid}",
        "custom": custom_metadata,
    }
    insert_stmt = pg_insert(projects_metadata).values(**data)
    upsert_stmt = insert_stmt.on_conflict_do_update(
        index_elements=[projects_metadata.c.project_uuid],
        set_=data,
    ).returning(sa.literal_column("*"))

    try:
        result: ResultProxy = await connection.execute(upsert_stmt)
        row: RowProxy | None = await result.first()
        assert row  # nosec
        return ProjectMetadata.model_validate(row)

    except ForeignKeyViolation as err:
        raise DBProjectNotFoundError(project_uuid=project_uuid) from err
