"""Utility functions for project document management.

This module contains common utilities for building and versioning project documents.
"""

from typing import cast

from aiohttp import web
from models_library.api_schemas_webserver.projects import (
    ProjectDocument,
    ProjectDocumentVersion,
)
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
from . import _projects_repository


async def build_project_document_and_increment_version(
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
    async def _build_project_document_and_increment_version() -> (
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

    return await _build_project_document_and_increment_version()
