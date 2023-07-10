from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from aiopg.sa.connection import SAConnection
from aiopg.sa.engine import Engine
from models_library.api_schemas_webserver.projects_metadata import MetadataDict
from models_library.projects import ProjectID
from pydantic import parse_obj_as
from simcore_postgres_database import utils_projects_metadata
from simcore_postgres_database.utils_projects_metadata import DBProjectNotFoundError

from .exceptions import ProjectNotFoundError


@asynccontextmanager
async def _acquire_and_handle(
    engine: Engine, project_uuid: ProjectID
) -> AsyncIterator[SAConnection]:
    try:
        async with engine.acquire() as connection:

            yield connection

    except DBProjectNotFoundError as err:
        raise ProjectNotFoundError(project_uuid=project_uuid) from err


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
) -> MetadataDict:
    """
    Raises:
        ProjectNotFoundError
        ValidationError: illegal metadata format in the database
    """
    async with _acquire_and_handle(engine, project_uuid) as connection:
        metadata = await utils_projects_metadata.upsert(
            connection, project_uuid=project_uuid, custom_metadata=custom_metadata
        )
        return parse_obj_as(MetadataDict, metadata.custom)
