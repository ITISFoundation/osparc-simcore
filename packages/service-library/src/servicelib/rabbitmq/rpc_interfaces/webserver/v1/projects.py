"""Projects RPC API subclient."""

from typing import Any
from uuid import UUID

from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.rest_pagination import PageOffsetInt
from models_library.rpc.webserver.projects import (
    ListProjectsMarkedAsJobRpcFilters,
    PageRpcProjectJobRpcGet,
    ProjectJobRpcGet,
)
from models_library.rpc_pagination import (
    DEFAULT_NUMBER_OF_ITEMS_PER_PAGE,
    PageLimitInt,
)
from models_library.users import UserID

from ._base import BaseRpcApi


class ProjectsRpcApi(BaseRpcApi):
    """RPC client for project-related operations."""

    async def get_project(
        self,
        *,
        product_name: ProductName,
        user_id: UserID,
        project_uuid: UUID,
        include: list[str] | None = None,
    ) -> dict[str, Any]:
        """Get a project by UUID."""
        return await self._request(
            "get_project",
            product_name=product_name,
            user_id=user_id,
            project_uuid=project_uuid,
            include=include or [],
        )

    async def list_projects(
        self,
        *,
        product_name: ProductName,
        user_id: UserID,
        filter_by_services: list[str] | None = None,
        filter_by_study_services: list[str] | None = None,
        offset: int = 0,
        limit: int | None = None,
        order_by: dict[str, str] | None = None,
        search: str | None = None,
    ) -> dict[str, Any]:
        """List projects for a user."""
        return await self._request(
            "list_projects",
            product_name=product_name,
            user_id=user_id,
            filter_by_services=filter_by_services or [],
            filter_by_study_services=filter_by_study_services or [],
            offset=offset,
            limit=limit,
            order_by=order_by or {},
            search=search,
        )

    async def create_project(
        self,
        *,
        product_name: ProductName,
        user_id: UserID,
        project: dict[str, Any],
        as_template: bool = False,
    ) -> dict[str, Any]:
        """Create a new project."""
        return await self._request(
            "create_project",
            product_name=product_name,
            user_id=user_id,
            project=project,
            as_template=as_template,
        )

    async def update_project(
        self,
        *,
        product_name: ProductName,
        user_id: UserID,
        project_uuid: UUID,
        project_patch: dict[str, Any],
    ) -> dict[str, Any]:
        """Update an existing project."""
        return await self._request(
            "update_project",
            product_name=product_name,
            user_id=user_id,
            project_uuid=project_uuid,
            project_patch=project_patch,
        )

    async def delete_project(
        self, *, product_name: ProductName, user_id: UserID, project_uuid: UUID
    ) -> None:
        """Delete a project."""
        return await self._request(
            "delete_project",
            product_name=product_name,
            user_id=user_id,
            project_uuid=project_uuid,
        )

    async def clone_project(
        self,
        *,
        product_name: ProductName,
        user_id: UserID,
        project_uuid: UUID,
        hidden: bool = False,
    ) -> dict[str, Any]:
        """Clone an existing project."""
        return await self._request(
            "clone_project",
            product_name=product_name,
            user_id=user_id,
            project_uuid=project_uuid,
            hidden=hidden,
        )

    async def mark_project_as_job(
        self,
        *,
        product_name: ProductName,
        user_id: UserID,
        project_uuid: ProjectID,
        job_parent_resource_name: str,
        storage_assets_deleted: bool,
    ) -> None:
        """Mark a project as a job."""
        return await self._request(
            "mark_project_as_job",
            product_name=product_name,
            user_id=user_id,
            project_uuid=project_uuid,
            job_parent_resource_name=job_parent_resource_name,
            storage_assets_deleted=storage_assets_deleted,
        )

    async def list_projects_marked_as_jobs(
        self,
        *,
        product_name: ProductName,
        user_id: UserID,
        offset: PageOffsetInt = 0,
        limit: PageLimitInt = DEFAULT_NUMBER_OF_ITEMS_PER_PAGE,
        filters: ListProjectsMarkedAsJobRpcFilters | None = None,
    ) -> PageRpcProjectJobRpcGet:
        """List projects marked as jobs."""
        return await self._request(
            "list_projects_marked_as_jobs",
            product_name=product_name,
            user_id=user_id,
            offset=offset,
            limit=limit,
            filters=filters,
        )

    async def get_project_marked_as_job(
        self,
        *,
        product_name: ProductName,
        user_id: UserID,
        project_uuid: ProjectID,
        job_parent_resource_name: str,
    ) -> ProjectJobRpcGet:
        """Get a project marked as a job."""
        return await self._request(
            "get_project_marked_as_job",
            product_name=product_name,
            user_id=user_id,
            project_uuid=project_uuid,
            job_parent_resource_name=job_parent_resource_name,
        )
