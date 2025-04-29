from common_library.pagination_tools import iter_pagination_params
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
from models_library.services_history import ServiceRelease
from models_library.users import UserID
from packaging.version import Version
from pydantic import NonNegativeInt, PositiveInt
from simcore_service_api_server.exceptions.custom_errors import (
    SolverServiceListJobsFiltersError,
)

from ._service_jobs import JobService
from .models.api_resources import compose_resource_name
from .models.schemas.jobs import Job
from .models.schemas.solvers import Solver, SolverKeyId
from .services_rpc.catalog import CatalogService

DEFAULT_PAGINATION_LIMIT = MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE - 1


class SolverService:
    _catalog_service: CatalogService
    _job_service: JobService

    def __init__(
        self,
        catalog_service: CatalogService,
        job_service: JobService,
    ):
        self._catalog_service = catalog_service
        self._job_service = job_service

    async def get_solver(
        self,
        *,
        product_name: ProductName,
        user_id: UserID,
        solver_key: SolverKeyId,
        solver_version: VersionStr,
    ) -> Solver:
        service = await self._catalog_service.get(
            user_id=user_id,
            name=solver_key,
            version=solver_version,
            product_name=product_name,
        )
        assert (  # nosec
            service.service_type == ServiceType.COMPUTATIONAL
        ), "Expected by SolverName regex"

        return Solver.create_from_service(service)

    async def get_latest_release(
        self,
        *,
        product_name: str,
        user_id: int,
        solver_key: SolverKeyId,
    ) -> Solver:
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
        # filters
        solver_key: SolverKeyId | None = None,
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
        if solver_key:
            collection_or_resource_ids.append(solver_key)
            if solver_version:
                collection_or_resource_ids.append("releases")
                collection_or_resource_ids.append(solver_version)
        elif solver_version:
            raise SolverServiceListJobsFiltersError

        job_parent_resource_name_prefix = compose_resource_name(
            *collection_or_resource_ids
        )

        # Use the common implementation from JobService
        return await self._job_service.list_jobs_by_resource_prefix(
            offset=offset,
            limit=limit,
            job_parent_resource_name_prefix=job_parent_resource_name_prefix,
        )

    async def solver_release_history(
        self,
        *,
        user_id: UserID,
        solver_key: SolverKeyId,
        product_name: ProductName,
        offset: NonNegativeInt,
        limit: PositiveInt,
    ) -> tuple[list[Solver], PageMetaInfoLimitOffset]:

        releases, page_meta = await self._catalog_service.list_release_history(
            user_id=user_id,
            service_key=solver_key,
            product_name=product_name,
            offset=offset,
            limit=limit,
        )

        service_instance = await self._catalog_service.get(
            user_id=user_id,
            name=solver_key,
            version=releases[-1].version,
            product_name=product_name,
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

    async def latest_solvers(
        self,
        *,
        user_id: UserID,
        product_name: ProductName,
        offset: NonNegativeInt,
        limit: PositiveInt,
    ) -> tuple[list[Solver], PageMetaInfoLimitOffset]:
        """Lists the latest solvers with pagination."""
        services, page_meta = await self._catalog_service.list_latest_releases(
            user_id=user_id,
            product_name=product_name,
            offset=offset,
            limit=limit,
            filters=ServiceListFilters(service_type=ServiceType.COMPUTATIONAL),
        )

        solvers = [Solver.create_from_service(service) for service in services]
        return solvers, page_meta
