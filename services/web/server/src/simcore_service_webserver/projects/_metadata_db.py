from aiopg.sa.engine import Engine
from models_library.api_schemas_webserver.projects_metadata import MetadataDict
from models_library.projects import ProjectID
from models_library.users import UserID


async def get_project_metadata(
    engine: Engine, user_id: UserID, project_uuid: ProjectID
) -> MetadataDict:
    raise NotImplementedError


async def upsert_project_metadata(
    engine: Engine, user_id: UserID, project_id: ProjectID, metadata: MetadataDict
) -> MetadataDict:
    raise NotImplementedError
