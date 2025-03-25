import functools
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from aiopg.sa.engine import Engine
from models_library.api_schemas_webserver.projects_metadata import MetadataDict
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from pydantic import TypeAdapter
from simcore_postgres_database import utils_projects_metadata
from simcore_postgres_database.utils_projects_metadata import (
    DBProjectInvalidAncestorsError,
    DBProjectInvalidParentNodeError,
    DBProjectInvalidParentProjectError,
    DBProjectNotFoundError,
)
from simcore_postgres_database.utils_projects_nodes import (
    ProjectNodesNodeNotFoundError,
    ProjectNodesNonUniqueNodeFoundError,
    ProjectNodesRepo,
)

from .exceptions import (
    NodeNotFoundError,
    ParentNodeNotFoundError,
    ParentProjectNotFoundError,
    ProjectInvalidUsageError,
    ProjectNotFoundError,
)

F = TypeVar("F", bound=Callable[..., Awaitable[Any]])


def _handle_projects_metadata_exceptions(fct: F) -> F:
    """Transforms project errors -> http errors"""

    @functools.wraps(fct)
    async def wrapper(*args, **kwargs) -> Any:
        try:
            return await fct(*args, **kwargs)

        except DBProjectNotFoundError as err:
            raise ProjectNotFoundError(project_uuid=err.project_uuid) from err  # type: ignore[attr-defined] # context defined in pydantic error # pylint: disable=no-member
        except ProjectNodesNodeNotFoundError as err:
            raise NodeNotFoundError(
                project_uuid=err.project_uuid, node_uuid=err.node_id  # type: ignore[attr-defined] # context defined in pydantic error # pylint: disable=no-member
            ) from err
        except ProjectNodesNonUniqueNodeFoundError as err:
            raise ProjectInvalidUsageError from err
        except DBProjectInvalidParentNodeError as err:
            raise ParentNodeNotFoundError(
                project_uuid=err.project_uuid, node_uuid=err.parent_node_id  # type: ignore[attr-defined] # context defined in pydantic error # pylint: disable=no-member
            ) from err

        except DBProjectInvalidParentProjectError as err:
            raise ParentProjectNotFoundError(
                project_uuid=err.parent_project_uuid  # type: ignore[attr-defined] # context defined in pydantic error # pylint: disable=no-member
            ) from err
        except DBProjectInvalidAncestorsError as err:
            raise ProjectInvalidUsageError from err

    return wrapper  # type: ignore


@_handle_projects_metadata_exceptions
async def get_project_id_from_node_id(engine: Engine, *, node_id: NodeID) -> ProjectID:
    async with engine.acquire() as connection:
        return await ProjectNodesRepo.get_project_id_from_node_id(
            connection, node_id=node_id
        )


@_handle_projects_metadata_exceptions
async def get_project_custom_metadata(
    engine: Engine, project_uuid: ProjectID
) -> MetadataDict:
    """
    Raises:
        ProjectNotFoundError
        ValidationError: illegal metadata format in the database
    """
    async with engine.acquire() as connection:
        metadata = await utils_projects_metadata.get(
            connection, project_uuid=project_uuid
        )
        # NOTE: if no metadata in table, it returns None  -- which converts here to --> {}
        return TypeAdapter(MetadataDict).validate_python(metadata.custom or {})


@_handle_projects_metadata_exceptions
async def set_project_custom_metadata(
    engine: Engine,
    project_uuid: ProjectID,
    custom_metadata: MetadataDict,
) -> MetadataDict:
    """
    Raises:
        ProjectNotFoundError
    """
    async with engine.acquire() as connection:
        metadata = await utils_projects_metadata.set_project_custom_metadata(
            connection,
            project_uuid=project_uuid,
            custom_metadata=custom_metadata,
        )

        return TypeAdapter(MetadataDict).validate_python(metadata.custom)


@_handle_projects_metadata_exceptions
async def project_has_ancestors(engine: Engine, *, project_uuid: ProjectID) -> bool:
    async with engine.acquire() as connection:
        metadata = await utils_projects_metadata.get(
            connection, project_uuid=project_uuid
        )
    return bool(metadata.parent_project_uuid is not None)


@_handle_projects_metadata_exceptions
async def set_project_ancestors(
    engine: Engine,
    *,
    project_uuid: ProjectID,
    parent_project_uuid: ProjectID | None,
    parent_node_id: NodeID | None,
) -> None:
    """
    Raises:
        ProjectNotFoundError
        NodeNotFoundError
        ParentNodeNotFoundError
        ProjectInvalidUsageError
        ValidationError: illegal metadata format in the database
    """

    async with engine.acquire() as connection:
        if parent_project_uuid and (parent_project_uuid == project_uuid):
            # this is not allowed!
            msg = "Project cannot be parent of itself"
            raise ProjectInvalidUsageError(msg)

        await utils_projects_metadata.set_project_ancestors(
            connection,
            project_uuid=project_uuid,
            parent_project_uuid=parent_project_uuid,
            parent_node_id=parent_node_id,
        )
