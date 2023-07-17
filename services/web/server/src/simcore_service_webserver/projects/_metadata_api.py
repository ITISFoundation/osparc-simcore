from aiohttp import web
from models_library.api_schemas_webserver.projects_metadata import MetadataDict
from models_library.projects import ProjectID
from models_library.users import UserID

from ..db.plugin import get_database_engine
from . import _metadata_db
from ._access_rights_api import validate_project_ownership


async def get_project_metadata(
    app: web.Application, user_id: UserID, project_uuid: ProjectID
) -> MetadataDict:
    await validate_project_ownership(app, user_id=user_id, project_uuid=project_uuid)

    return await _metadata_db.get_project_metadata(
        engine=get_database_engine(app), project_uuid=project_uuid
    )


async def set_project_custom_metadata(
    app: web.Application, user_id: UserID, project_uuid: ProjectID, value: MetadataDict
) -> MetadataDict:
    await validate_project_ownership(app, user_id=user_id, project_uuid=project_uuid)

    return await _metadata_db.set_project_metadata(
        engine=get_database_engine(app),
        project_uuid=project_uuid,
        custom_metadata=value,
    )
