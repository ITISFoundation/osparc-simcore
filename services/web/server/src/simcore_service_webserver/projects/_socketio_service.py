from typing import Final

from aiohttp import web
from models_library.api_schemas_webserver.projects import ProjectDocument
from models_library.groups import GroupID
from models_library.projects import ProjectID
from models_library.socketio import SocketMessageDict
from pydantic import AliasGenerator, BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from ..socketio.messages import send_message_to_project_room

SOCKET_IO_PROJECT_DOCUMENT_UPDATED_EVENT: Final[str] = "projectDocument:updated"


class BaseEvent(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True,
        alias_generator=AliasGenerator(
            serialization_alias=to_camel,
        ),
    )


class ProjectDocumentEvent(BaseEvent):
    project_id: ProjectID
    user_primary_gid: GroupID
    client_session_id: str | None
    version: int
    document: ProjectDocument


async def notify_project_document_updated(
    app: web.Application,
    *,
    project_id: ProjectID,
    user_primary_gid: GroupID,
    client_session_id: str | None,
    version: int,
    document: ProjectDocument,
) -> None:
    notification_message = SocketMessageDict(
        event_type=SOCKET_IO_PROJECT_DOCUMENT_UPDATED_EVENT,
        data={
            **ProjectDocumentEvent(
                project_id=project_id,
                user_primary_gid=user_primary_gid,
                client_session_id=client_session_id,
                version=version,
                document=document,
            ).model_dump(mode="json", by_alias=True),
        },
    )
    await send_message_to_project_room(app, project_id, notification_message)
