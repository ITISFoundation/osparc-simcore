from aiopg.sa.engine import Engine
from models_library.api_schemas_webserver.projects_metadata import MetadataDict
from models_library.projects import ProjectID
from pydantic import parse_obj_as
from simcore_postgres_database.utils_projects_metadata import (
    DBProjectNotFoundError,
    ProjectMetadataRepo,
)


async def get_project_metadata(engine: Engine, project_uuid: ProjectID) -> MetadataDict:
    """
    Raises:
        ProjectNotFoundError
    """
    async with engine.acquire() as connection:
        pm = await ProjectMetadataRepo.get(connection, project_uuid=project_uuid)
        return parse_obj_as(MetadataDict, pm.custom_metadata)


async def upsert_project_metadata(
    engine: Engine,
    project_uuid: ProjectID,
    custom_metadata: MetadataDict,
) -> MetadataDict:
    async with engine.acquire() as connection:
        project_metadata = await ProjectMetadataRepo.upsert(
            connection, project_uuid=project_uuid, custom_metadata=custom_metadata
        )
        return parse_obj_as(MetadataDict, project_metadata.custom_metadata)


assert DBProjectNotFoundError  # nosec
__all__: tuple[str, ...] = ("DBProjectNotFoundError",)
