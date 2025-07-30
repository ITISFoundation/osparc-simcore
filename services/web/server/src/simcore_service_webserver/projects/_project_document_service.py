"""Utility functions for project document management.

This module contains common utilities for building and versioning project documents.
"""

import logging
import re
from typing import cast

from aiohttp import web
from models_library.api_schemas_webserver.projects import (
    ProjectDocument,
    ProjectDocumentVersion,
)
from models_library.api_schemas_webserver.socketio import SocketIORoomStr
from models_library.projects import ProjectID, ProjectTemplateType
from models_library.projects import ProjectType as ProjectTypeAPI
from servicelib.redis import (
    PROJECT_DB_UPDATE_REDIS_LOCK_KEY,
    exclusive,
    increment_and_return_project_document_version,
)

from ..redis import (
    get_redis_document_manager_client_sdk,
    get_redis_lock_manager_client_sdk,
)
from ..resource_manager.registry import get_registry
from ..resource_manager.registry_utils import list_opened_project_ids
from ..socketio._utils import get_socket_server
from . import _projects_repository

_logger = logging.getLogger(__name__)


async def create_project_document_and_increment_version(
    app: web.Application, project_uuid: ProjectID
) -> tuple[ProjectDocument, ProjectDocumentVersion]:
    """Build project document and increment version with Redis lock protection.

    This function is protected by Redis exclusive lock because:
    - the project document and its version must be kept in sync

    Args:
        app: The web application instance
        project_uuid: UUID of the project

    Returns:
        Tuple containing the project document and its version number
    """

    @exclusive(
        get_redis_lock_manager_client_sdk(app),
        lock_key=PROJECT_DB_UPDATE_REDIS_LOCK_KEY.format(project_uuid),
        blocking=True,
        blocking_timeout=None,  # NOTE: this is a blocking call, a timeout has undefined effects
    )
    async def _create_project_document_and_increment_version() -> (
        tuple[ProjectDocument, int]
    ):
        """This function is protected because
        - the project document and its version must be kept in sync
        """
        # Get the full project with workbench for document creation
        project_with_workbench = await _projects_repository.get_project_with_workbench(
            app=app, project_uuid=project_uuid
        )
        # Create project document
        project_document = ProjectDocument(
            uuid=project_with_workbench.uuid,
            workspace_id=project_with_workbench.workspace_id,
            name=project_with_workbench.name,
            description=project_with_workbench.description,
            thumbnail=project_with_workbench.thumbnail,
            last_change_date=project_with_workbench.last_change_date,
            classifiers=project_with_workbench.classifiers,
            dev=project_with_workbench.dev,
            quality=project_with_workbench.quality,
            workbench=project_with_workbench.workbench,
            ui=project_with_workbench.ui,
            type=cast(ProjectTypeAPI, project_with_workbench.type),
            template_type=cast(
                ProjectTemplateType, project_with_workbench.template_type
            ),
        )
        # Increment document version
        redis_client_sdk = get_redis_document_manager_client_sdk(app)
        document_version = await increment_and_return_project_document_version(
            redis_client=redis_client_sdk, project_uuid=project_uuid
        )

        return project_document, document_version

    return await _create_project_document_and_increment_version()


async def remove_project_documents_as_admin(app: web.Application) -> None:
    """Admin function to clean up project documents for projects with no connected users.

    This function scans through all project documents in the Redis DOCUMENTS database,
    checks if there are any users currently connected to the project room via socketio,
    and removes documents that have no connected users.
    """
    # Get Redis document manager client to access the DOCUMENTS database
    redis_client = get_redis_document_manager_client_sdk(app)

    # Pattern to match project document keys - looking for keys that contain project UUIDs
    project_document_pattern = "projects:*:version"

    # Get socketio server instance
    sio = get_socket_server(app)

    # Get known opened projects ids based on Redis resources table
    registry = get_registry(app)
    known_opened_project_ids = await list_opened_project_ids(registry)
    known_opened_project_ids = set(known_opened_project_ids)

    projects_removed = 0

    # Scan through all project document keys
    async for key in redis_client.redis.scan_iter(
        match=project_document_pattern, count=1000
    ):
        # Extract project UUID from the key pattern "projects:{project_uuid}:version"
        key_str = key.decode("utf-8") if isinstance(key, bytes) else key
        match = re.match(r"projects:([0-9a-f-]+):version", key_str)

        if not match:
            continue

        project_uuid_str = match.group(1)
        project_uuid = ProjectID(project_uuid_str)
        project_room = SocketIORoomStr.from_project_id(project_uuid)

        # 1. CHECK - Check if the project UUID is in the known opened projects
        if project_uuid in known_opened_project_ids:
            _logger.debug(
                "Project %s is in Redis Resources table (which means Project is opened), keeping document",
                project_uuid,
            )
            continue

        # 2. CHECK - Check if there are any users connected to this project room
        try:
            # Get all session IDs (socket IDs) in the project room
            room_sessions = list(
                sio.manager.get_participants(namespace="/", room=project_room)
            )

            # If no users are connected to this project room, remove the document
            if not room_sessions:
                await redis_client.redis.delete(key_str)
                projects_removed += 1
                _logger.info(
                    "Removed project document for project %s (no connected users)",
                    project_uuid,
                )
            else:
                _logger.error(
                    "Project %s has %d connected users in the socket io room (This is not expected, as project resource is not in the Redis Resources table), keeping document just in case",
                    project_uuid,
                    len(room_sessions),
                )

        except (KeyError, AttributeError, ValueError):
            _logger.exception(
                "Failed to check room participants for project %s",
                project_uuid,
            )
            continue

    _logger.info(
        "Project document cleanup completed: removed %d project documents",
        projects_removed,
    )
