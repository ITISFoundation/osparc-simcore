from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from aiopg.sa.connection import SAConnection
from aiopg.sa.engine import Engine
from models_library.api_schemas_webserver.projects_metadata import MetadataDict
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from pydantic import parse_obj_as
from simcore_postgres_database import utils_projects_metadata
from simcore_postgres_database.utils_projects_metadata import (
    DBProjectNodeParentNotFoundError,
    DBProjectNotFoundError,
)
from simcore_postgres_database.utils_projects_nodes import (
    ProjectNodesNodeNotFound,
    ProjectNodesRepo,
)

from .exceptions import ParentNodeNotFoundError, ProjectNotFoundError


@asynccontextmanager
async def _acquire_and_handle(
    engine: Engine, project_uuid: ProjectID
) -> AsyncIterator[SAConnection]:
    try:
        async with engine.acquire() as connection:

            yield connection

    except DBProjectNotFoundError as err:
        raise ProjectNotFoundError(project_uuid=project_uuid) from err
    except DBProjectNodeParentNotFoundError as err:
        project_id, node_id = err.args[0]
        raise ParentNodeNotFoundError(
            project_uuid=project_id, node_uuid=node_id
        ) from err


async def get_project_metadata(engine: Engine, project_uuid: ProjectID) -> MetadataDict:
    """
    Raises:
        ProjectNotFoundError
        ValidationError: illegal metadata format in the database
    """
    async with _acquire_and_handle(engine, project_uuid) as connection:
        metadata = await utils_projects_metadata.get(
            connection, project_uuid=project_uuid
        )
        # NOTE: if no metadata in table, it returns None  -- which converts here to --> {}
        return parse_obj_as(MetadataDict, metadata.custom or {})


async def set_project_metadata(
    engine: Engine,
    project_uuid: ProjectID,
    custom_metadata: MetadataDict,
    parent_node_id: NodeID | None,
) -> MetadataDict:
    """
    Raises:
        ProjectNotFoundError
        NodeNotFoundError
        ValidationError: illegal metadata format in the database
    """
    parent_project_uuid: ProjectID | None = None
    if parent_node_id is None and (parent_node_idstr := custom_metadata.get("node_id")):
        # NOTE: backward compatibility with S4l old client
        parent_node_id = parse_obj_as(NodeID, parent_node_idstr)

    async with _acquire_and_handle(engine, project_uuid) as connection:
        if parent_node_id:
            try:
                parent_project_uuid = (
                    await ProjectNodesRepo.get_project_id_from_node_id(
                        connection, node_id=parent_node_id
                    )
                )
            except ProjectNodesNodeNotFound as err:
                raise DBProjectNodeParentNotFoundError((None, parent_node_id)) from err
        metadata = await utils_projects_metadata.upsert(
            connection,
            project_uuid=project_uuid,
            custom_metadata=custom_metadata,
            parent_project_uuid=parent_project_uuid,
            parent_node_id=parent_node_id,
        )
        return parse_obj_as(MetadataDict, metadata.custom)
