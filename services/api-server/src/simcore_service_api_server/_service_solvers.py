from typing import Annotated

from common_library.pagination_tools import iter_pagination_params
from fastapi import Depends
from models_library.basic_types import VersionStr
from models_library.products import ProductName
from models_library.projects_nodes import Node
from models_library.rest_pagination import (
    MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE,
    PageMetaInfoLimitOffset,
    PageOffsetInt,
)
from models_library.rpc_pagination import PageLimitInt
from models_library.services_enums import ServiceType
from models_library.services_history import ServiceRelease
from models_library.users import UserID
from packaging.version import Version

from .api.dependencies.webserver_rpc import get_wb_api_rpc_client
from .models.api_resources import compose_resource_name
from .models.schemas.jobs import Job, JobInputs
from .models.schemas.solvers import Solver, SolverKeyId
from .services_http.solver_job_models_converters import (
    create_job_inputs_from_node_inputs,
)
from .services_rpc.catalog import CatalogService
from .services_rpc.wb_api_server import WbApiRpcClient

DEFAULT_PAGINATION_LIMIT = MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE - 1


class SolverService:
    _catalog_service: CatalogService
    _webserver_client: WbApiRpcClient

    def __init__(
        self,
        catalog_service: Annotated[CatalogService, Depends()],
        webserver_client: Annotated[WbApiRpcClient, Depends(get_wb_api_rpc_client)],
    ):
        self._catalog_service = catalog_service
        self._webserver_client = webserver_client

    async def get_solver(
        self,
        *,
        user_id: UserID,
        name: SolverKeyId,
        version: VersionStr,
        product_name: ProductName,
    ) -> Solver:
        service = await self._catalog_service.get(
            user_id=user_id,
            name=name,
            version=version,
            product_name=product_name,
        )
        assert (  # nosec
            service.service_type == ServiceType.COMPUTATIONAL
        ), "Expected by SolverName regex"

        return Solver.create_from_service(service)

    async def get_latest_release(
        self,
        *,
        user_id: int,
        solver_key: SolverKeyId,
        product_name: str,
    ) -> Solver:
        # TODO: Mads, this is not necessary. The first item is the latest!
        service_releases: list[ServiceRelease] = []
        for page_params in iter_pagination_params(limit=DEFAULT_PAGINATION_LIMIT):
            releases, page_meta = await self._catalog_service.list_release_history(
                user_id=user_id,
                service_key=solver_key,
                product_name=product_name,
                offset=page_params.offset,
                limit=page_params.limit,
            )
            page_params.total_number_of_items = page_meta.total
            service_releases.extend(releases)

        release = sorted(service_releases, key=lambda s: Version(s.version))[-1]
        service = await self._catalog_service.get(
            user_id=user_id,
            name=solver_key,
            version=release.version,
            product_name=product_name,
        )

        return Solver.create_from_service(service)

    async def list_jobs(
        self,
        *,
        user_id: UserID,
        product_name: ProductName,
        # filters
        solver_id: SolverKeyId | None = None,
        solver_version: VersionStr | None = None,
        # pagination
        offset: PageOffsetInt = 0,
        limit: PageLimitInt = DEFAULT_PAGINATION_LIMIT,
    ) -> tuple[list[Job], PageMetaInfoLimitOffset]:
        """Lists all solver jobs for a user with pagination"""

        # 1. Compose job parent resource name prefix
        collection_or_resource_ids = [
            "solvers",  # solver_id, "releases", solver_version, "jobs",
        ]
        if solver_id:
            collection_or_resource_ids.append(solver_id)
            if solver_version:
                collection_or_resource_ids.append("releases")
                collection_or_resource_ids.append(solver_version)
        elif solver_version:
            msg = "solver_version is set but solver_id is not. Please provide both or none of them"
            raise ValueError(msg)

        job_parent_resource_name_prefix = compose_resource_name(
            *collection_or_resource_ids
        )

        # 2. List projects marked as jobs
        projects_page = await self._webserver_client.list_projects_marked_as_jobs(
            product_name=product_name,
            user_id=user_id,
            offset=offset,
            limit=limit,
            job_parent_resource_name_prefix=job_parent_resource_name_prefix,
        )

        # 3. Convert projects to jobs
        jobs: list[Job] = []
        for project_job in projects_page.data:

            assert (  # nosec
                len(project_job.workbench) == 1
            ), "Expected only one solver node in workbench"

            solver_node: Node = next(iter(project_job.workbench.values()))
            job_inputs: JobInputs = create_job_inputs_from_node_inputs(
                inputs=solver_node.inputs or {}
            )
            assert project_job.job_parent_resource_name  # nosec

            jobs.append(
                Job(
                    id=project_job.uuid,
                    name=Job.compose_resource_name(
                        project_job.job_parent_resource_name, project_job.uuid
                    ),
                    inputs_checksum=job_inputs.compute_checksum(),
                    created_at=project_job.created_at,
                    runner_name=project_job.job_parent_resource_name,
                    url=None,
                    runner_url=None,
                    outputs_url=None,
                )
            )

        return jobs, projects_page.meta
