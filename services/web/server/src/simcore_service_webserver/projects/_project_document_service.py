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
from servicelib.logging_errors import create_troubleshootting_log_kwargs
from servicelib.logging_utils import log_context
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
from ..resource_manager.service import list_opened_project_ids
from ..socketio._utils import get_socket_server
from . import _projects_nodes_repository, _projects_repository

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
        project = await _projects_repository.get_project(
            app=app, project_uuid=project_uuid
        )
        project_nodes = await _projects_nodes_repository.get_by_project(
            app=app, project_id=project_uuid
        )
        workbench = {f"{node_id}": node for node_id, node in project_nodes}

        # Create project document
        project_document = ProjectDocument(
            uuid=project.uuid,
            workspace_id=project.workspace_id,
            name=project.name,
            description=project.description,
            thumbnail=project.thumbnail,
            last_change_date=project.last_change_date,
            classifiers=project.classifiers,
            dev=project.dev,
            quality=project.quality,
            workbench=workbench,
            ui=project.ui,
            type=cast(ProjectTypeAPI, project.type),
            template_type=cast(ProjectTemplateType, project.template_type),
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
    with log_context(
        _logger,
        logging.INFO,
        msg="Project document cleanup started",
    ):
        # Get Redis document manager client to access the DOCUMENTS database
        redis_client = get_redis_document_manager_client_sdk(app)

        # Pattern to match project document keys - looking for keys that contain project UUIDs
        project_document_pattern = "projects:*:version"

        # Get socketio server instance
        sio = get_socket_server(app)

        # Get known opened projects ids based on Redis resources table
        registry = get_registry(app)
        known_opened_project_ids = await list_opened_project_ids(registry)
        known_opened_project_ids_set = set(known_opened_project_ids)

        projects_removed = 0

        # Scan through all project document keys
        async for key in redis_client.redis.scan_iter(
            match=project_document_pattern, count=1000
        ):
            # Extract project UUID from the key pattern "projects:{project_uuid}:version"
            key_str = key.decode("utf-8") if isinstance(key, bytes) else key
            match = re.match(r"projects:(?P<project_uuid>[0-9a-f-]+):version", key_str)

            if not match:
                continue

            project_uuid_str = match.group("project_uuid")
            project_uuid = ProjectID(project_uuid_str)
            project_room = SocketIORoomStr.from_project_id(project_uuid)

            # 1. CHECK - Check if the project UUID is in the known opened projects
            if project_uuid in known_opened_project_ids_set:
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
                    # Create a synthetic exception for this unexpected state
                    unexpected_state_error = RuntimeError(
                        f"Project {project_uuid} has {len(room_sessions)} connected users but is not in Redis Resources table"
                    )
                    _logger.error(
                        **create_troubleshootting_log_kwargs(
                            user_error_msg=f"Project {project_uuid} has {len(room_sessions)} connected users in the socket io room (This is not expected, as project resource is not in the Redis Resources table), keeping document just in case",
                            error=unexpected_state_error,
                            error_context={
                                "project_uuid": str(project_uuid),
                                "project_room": project_room,
                                "key_str": key_str,
                                "connected_users_count": len(room_sessions),
                                "room_sessions": room_sessions[
                                    :5
                                ],  # Limit to first 5 sessions for debugging
                            },
                            tip="This indicates a potential race condition or inconsistency between the Redis Resources table and socketio room state. Check if the project was recently closed but users are still connected, or if there's a synchronization issue between services.",
                        )
                    )
                    continue

            except (KeyError, AttributeError, ValueError) as exc:
                _logger.exception(
                    **create_troubleshootting_log_kwargs(
                        user_error_msg=f"Failed to check room participants for project {project_uuid}",
                        error=exc,
                        error_context={
                            "project_uuid": str(project_uuid),
                            "project_room": project_room,
                            "key_str": key_str,
                        },
                        tip="Check if socketio server is properly initialized and the room exists. This could indicate a socketio manager issue or invalid room format.",
                    )
                )
                continue

        _logger.info("Completed: removed %d project documents", projects_removed)
