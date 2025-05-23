from dataclasses import dataclass

from models_library.api_schemas_catalog.services import ServiceListFilters
from models_library.basic_types import VersionStr
from models_library.products import ProductName
from models_library.rest_pagination import (
    MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE,
    PageMetaInfoLimitOffset,
    PageOffsetInt,
)
from models_library.rpc_pagination import PageLimitInt
from models_library.services_enums import ServiceType
from models_library.users import UserID
from simcore_service_api_server.models.basic_types import NameValueTuple

from ._service_jobs import JobService
from ._service_utils import check_user_product_consistency
from .exceptions.backend_errors import (
    ProgramOrSolverOrStudyNotFoundError,
)
from .exceptions.custom_errors import (
    SolverServiceListJobsFiltersError,
)
from .models.api_resources import compose_resource_name
from .models.schemas.jobs import Job
from .models.schemas.solvers import Solver, SolverKeyId
from .services_rpc.catalog import CatalogService

DEFAULT_PAGINATION_LIMIT = MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE - 1


@dataclass(frozen=True, kw_only=True)
class SolverService:
    catalog_service: CatalogService
    job_service: JobService
    user_id: UserID
    product_name: ProductName

    def __post_init__(self):
        check_user_product_consistency(
            service_cls_name=self.__class__.__name__,
            service_provider=self.catalog_service,
            user_id=self.user_id,
            product_name=self.product_name,
        )

        check_user_product_consistency(
            service_cls_name=self.__class__.__name__,
            service_provider=self.job_service,
            user_id=self.user_id,
            product_name=self.product_name,
        )

    async def get_solver(
        self,
        *,
        solver_key: SolverKeyId,
        solver_version: VersionStr,
    ) -> Solver:
        service = await self.catalog_service.get(
            name=solver_key,
            version=solver_version,
        )
        assert (  # nosec
            service.service_type == ServiceType.COMPUTATIONAL
        ), "Expected by SolverName regex"

        return Solver.create_from_service(service)

    async def get_latest_release(
        self,
        *,
        solver_key: SolverKeyId,
    ) -> Solver:
        releases, _ = await self.catalog_service.list_release_history_latest_first(
            filter_by_service_key=solver_key,
            pagination_offset=0,
            pagination_limit=1,
        )

        if len(releases) == 0:
            raise ProgramOrSolverOrStudyNotFoundError(name=solver_key, version="latest")
        service = await self.catalog_service.get(
            name=solver_key,
            version=releases[0].version,
        )

        return Solver.create_from_service(service)

    async def list_jobs(
        self,
        *,
        pagination_offset: PageOffsetInt | None = None,
        pagination_limit: PageLimitInt | None = None,
        filter_by_solver_key: SolverKeyId | None = None,
        filter_by_solver_version: VersionStr | None = None,
        filter_any_custom_metadata: list[NameValueTuple] | None = None,
    ) -> tuple[list[Job], PageMetaInfoLimitOffset]:
        """Lists all solver jobs for a user with pagination"""

        # 1. Compose job parent resource name prefix
        collection_or_resource_ids = [
            "solvers",  # solver_id, "releases", solver_version, "jobs",
        ]
        if filter_by_solver_key:
            collection_or_resource_ids.append(filter_by_solver_key)
            if filter_by_solver_version:
                collection_or_resource_ids.append("releases")
                collection_or_resource_ids.append(filter_by_solver_version)
        elif filter_by_solver_version:
            raise SolverServiceListJobsFiltersError

        job_parent_resource_name = compose_resource_name(*collection_or_resource_ids)

        # 2. list jobs under job_parent_resource_name
        return await self.job_service.list_jobs(
            job_parent_resource_name=job_parent_resource_name,
            filter_any_custom_metadata=filter_any_custom_metadata,
            pagination_offset=pagination_offset,
            pagination_limit=pagination_limit,
        )

    async def solver_release_history(
        self,
        *,
        solver_key: SolverKeyId,
        pagination_offset: PageOffsetInt | None = None,
        pagination_limit: PageLimitInt | None = None,
    ) -> tuple[list[Solver], PageMetaInfoLimitOffset]:

        releases, page_meta = (
            await self.catalog_service.list_release_history_latest_first(
                filter_by_service_key=solver_key,
                pagination_offset=pagination_offset,
                pagination_limit=pagination_limit,
            )
        )

        service_instance = await self.catalog_service.get(
            name=solver_key,
            version=releases[-1].version,
        )

        return [
            Solver.create_from_service_release(
                service_key=service_instance.key,
                description=service_instance.description,
                contact=service_instance.contact,
                name=service_instance.name,
                service=service,
            )
            for service in releases
        ], page_meta

    async def list_all_solvers(
        self,
        *,
        pagination_offset: PageOffsetInt | None = None,
        pagination_limit: PageLimitInt | None = None,
        filter_by_solver_key_pattern: str | None = None,
        filter_by_version_display_pattern: str | None = None,
    ) -> tuple[list[Solver], PageMetaInfoLimitOffset]:
        """Lists all solvers with pagination and filtering, including all versions.

        Unlike `latest_solvers` which only shows the latest version of each solver,
        this method returns all versions of solvers that match the filters.

        Args:
            pagination_offset: Pagination offset
            pagination_limit: Pagination limit
            filter_by_solver_key_pattern: Optional pattern to filter solvers by key e.g. "simcore/service/my_solver*"
            filter_by_version_display_pattern: Optional pattern to filter by version display e.g. "1.0.*-beta"

        Returns:
            A tuple with the list of filtered solvers and pagination metadata
        """
        filters = ServiceListFilters(service_type=ServiceType.COMPUTATIONAL)

        # Add key_pattern filter for solver ID if provided
        if filter_by_solver_key_pattern:
            filters.service_key_pattern = filter_by_solver_key_pattern

        # Add version_display_pattern filter if provided
        if filter_by_version_display_pattern:
            filters.version_display_pattern = filter_by_version_display_pattern

        services, page_meta = await self.catalog_service.list_all_services_summaries(
            pagination_offset=pagination_offset,
            pagination_limit=pagination_limit,
            filters=filters,
        )

        solvers = [Solver.create_from_service(service) for service in services]
        return solvers, page_meta

    async def latest_solvers(
        self,
        *,
        pagination_offset: PageOffsetInt | None = None,
        pagination_limit: PageLimitInt | None = None,
        filter_by_solver_key_pattern: str | None = None,
        filter_by_version_display_pattern: str | None = None,
    ) -> tuple[list[Solver], PageMetaInfoLimitOffset]:
        """Lists the latest solvers with pagination and filtering.

        Args:
            pagination_offset: Pagination offset
            pagination_limit: Pagination limit
            filter_by_solver_key_pattern: Optional pattern to filter solvers by key e.g. "simcore/service/my_solver*"
            filter_by_version_display_pattern: Optional pattern to filter by version display e.g. "1.0.*-beta"

        Returns:
            A tuple with the list of filtered solvers and pagination metadata
        """
        filters = ServiceListFilters(service_type=ServiceType.COMPUTATIONAL)

        # Add key_pattern filter for solver ID if provided
        if filter_by_solver_key_pattern:
            filters.service_key_pattern = filter_by_solver_key_pattern

        # Add version_display_pattern filter if provided
        if filter_by_version_display_pattern:
            filters.version_display_pattern = filter_by_version_display_pattern

        services, page_meta = await self.catalog_service.list_latest_releases(
            pagination_offset=pagination_offset,
            pagination_limit=pagination_limit,
            filters=filters,
        )

        solvers = [Solver.create_from_service(service) for service in services]
        return solvers, page_meta
