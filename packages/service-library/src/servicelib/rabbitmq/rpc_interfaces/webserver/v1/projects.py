"""Projects RPC API subclient."""

from typing import cast

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
        await self._request(
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
        return cast(
            PageRpcProjectJobRpcGet,
            await self._request(
                "list_projects_marked_as_jobs",
                product_name=product_name,
                user_id=user_id,
                offset=offset,
                limit=limit,
                filters=filters,
            ),
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
        return cast(
            ProjectJobRpcGet,
            await self._request(
                "get_project_marked_as_job",
                product_name=product_name,
                user_id=user_id,
                project_uuid=project_uuid,
                job_parent_resource_name=job_parent_resource_name,
            ),
        )
