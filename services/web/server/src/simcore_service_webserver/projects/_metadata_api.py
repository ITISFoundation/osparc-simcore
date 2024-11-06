import logging
from typing import Final

from aiohttp import web
from models_library.api_schemas_webserver.projects_metadata import MetadataDict
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.users import UserID
from pydantic import TypeAdapter

from ..db.plugin import get_database_engine
from . import _metadata_db
from ._access_rights_api import validate_project_ownership

_logger = logging.getLogger(__name__)


async def get_project_custom_metadata(
    app: web.Application, user_id: UserID, project_uuid: ProjectID
) -> MetadataDict:
    await validate_project_ownership(app, user_id=user_id, project_uuid=project_uuid)

    return await _metadata_db.get_project_custom_metadata(
        engine=get_database_engine(app), project_uuid=project_uuid
    )


async def set_project_custom_metadata(
    app: web.Application,
    user_id: UserID,
    project_uuid: ProjectID,
    value: MetadataDict,
) -> MetadataDict:
    await validate_project_ownership(app, user_id=user_id, project_uuid=project_uuid)

    return await _metadata_db.set_project_custom_metadata(
        engine=get_database_engine(app),
        project_uuid=project_uuid,
        custom_metadata=value,
    )


_NIL_NODE_UUID: Final[NodeID] = NodeID(int=0)


async def _project_has_ancestors(
    app: web.Application, *, user_id: UserID, project_uuid: ProjectID
) -> bool:
    await validate_project_ownership(app, user_id=user_id, project_uuid=project_uuid)

    return await _metadata_db.project_has_ancestors(
        engine=get_database_engine(app), project_uuid=project_uuid
    )


async def set_project_ancestors_from_custom_metadata(
    app: web.Application,
    user_id: UserID,
    project_uuid: ProjectID,
    custom_metadata: MetadataDict,
) -> None:
    """NOTE: this should not be used anywhere else than from the metadata handler!"""
    await validate_project_ownership(app, user_id=user_id, project_uuid=project_uuid)
    if await _project_has_ancestors(app, user_id=user_id, project_uuid=project_uuid):
        # we do not override any existing ancestors via this method
        return

    if parent_node_idstr := custom_metadata.get("node_id"):
        # NOTE: backward compatibility with S4l old client
        parent_node_id = TypeAdapter(NodeID).validate_python(parent_node_idstr)

        if parent_node_id == _NIL_NODE_UUID:
            return

        # let's try to get the parent project UUID
        parent_project_uuid = await _metadata_db.get_project_id_from_node_id(
            get_database_engine(app), node_id=parent_node_id
        )

        await _metadata_db.set_project_ancestors(
            get_database_engine(app),
            project_uuid=project_uuid,
            parent_project_uuid=parent_project_uuid,
            parent_node_id=parent_node_id,
        )


async def set_project_ancestors(
    app: web.Application,
    user_id: UserID,
    project_uuid: ProjectID,
    parent_project_uuid: ProjectID | None,
    parent_node_id: NodeID | None,
) -> None:
    await validate_project_ownership(app, user_id=user_id, project_uuid=project_uuid)

    await _metadata_db.set_project_ancestors(
        get_database_engine(app),
        project_uuid=project_uuid,
        parent_project_uuid=parent_project_uuid,
        parent_node_id=parent_node_id,
    )
