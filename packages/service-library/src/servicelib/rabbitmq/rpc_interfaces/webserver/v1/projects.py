"""Projects RPC API subclient."""

from typing import Any
from uuid import UUID

from ._base import BaseRpcApi


class ProjectsRpcApi(BaseRpcApi):
    """RPC client for project-related operations."""

    async def get_project(
        self, user_id: int, project_uuid: UUID, *, include: list[str] | None = None
    ) -> dict[str, Any]:
        """Get a project by UUID."""
        return await self._request(
            "get_project",
            user_id=user_id,
            project_uuid=project_uuid,
            include=include or [],
        )

    async def list_projects(
        self,
        user_id: int,
        *,
        filter_by_services: list[str] | None = None,
        filter_by_study_services: list[str] | None = None,
        offset: int = 0,
        limit: int | None = None,
        order_by: dict[str, str] | None = None,
        search: str | None = None
    ) -> dict[str, Any]:
        """List projects for a user."""
        return await self._request(
            "list_projects",
            user_id=user_id,
            filter_by_services=filter_by_services or [],
            filter_by_study_services=filter_by_study_services or [],
            offset=offset,
            limit=limit,
            order_by=order_by or {},
            search=search,
        )

    async def create_project(
        self, user_id: int, project: dict[str, Any], *, as_template: bool = False
    ) -> dict[str, Any]:
        """Create a new project."""
        return await self._request(
            "create_project", user_id=user_id, project=project, as_template=as_template
        )

    async def update_project(
        self, user_id: int, project_uuid: UUID, project_patch: dict[str, Any]
    ) -> dict[str, Any]:
        """Update an existing project."""
        return await self._request(
            "update_project",
            user_id=user_id,
            project_uuid=project_uuid,
            project_patch=project_patch,
        )

    async def delete_project(self, user_id: int, project_uuid: UUID) -> None:
        """Delete a project."""
        return await self._request(
            "delete_project", user_id=user_id, project_uuid=project_uuid
        )

    async def clone_project(
        self, user_id: int, project_uuid: UUID, *, hidden: bool = False
    ) -> dict[str, Any]:
        """Clone an existing project."""
        return await self._request(
            "clone_project", user_id=user_id, project_uuid=project_uuid, hidden=hidden
        )
