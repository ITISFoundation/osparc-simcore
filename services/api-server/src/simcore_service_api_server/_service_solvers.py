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
from pydantic import NonNegativeInt, PositiveInt
from simcore_service_api_server.exceptions.backend_errors import (
    ProgramOrSolverOrStudyNotFoundError,
)
from simcore_service_api_server.exceptions.custom_errors import (
    SolverServiceListJobsFiltersError,
)

from ._service_jobs import JobService, check_user_product_consistency
from .models.api_resources import compose_resource_name
from .models.schemas.jobs import Job
from .models.schemas.solvers import Solver, SolverKeyId
from .services_rpc.catalog import CatalogService

DEFAULT_PAGINATION_LIMIT = MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE - 1


class SolverService:
    _catalog_service: CatalogService
    _job_service: JobService
    # context
    _user_id: UserID
    _product_name: ProductName

    def __init__(
        self,
        catalog_service: CatalogService,
        job_service: JobService,
        user_id: UserID,
        product_name: ProductName,
    ):
        self._catalog_service = catalog_service
        self._job_service = job_service

        # context
        check_user_product_consistency(
            service_cls_name=self.__class__.__name__,
            user_id=user_id,
            product_name=product_name,
            job_service=job_service,
        )

        self._user_id = user_id
        self._product_name = product_name

    async def get_solver(
        self,
        *,
        solver_key: SolverKeyId,
        solver_version: VersionStr,
    ) -> Solver:
        service = await self._catalog_service.get(
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
        releases, _ = await self._catalog_service.list_release_history_latest_first(
            service_key=solver_key,
            offset=0,
            limit=1,
        )

        if len(releases) == 0:
            raise ProgramOrSolverOrStudyNotFoundError(name=solver_key, version="latest")
        service = await self._catalog_service.get(
            name=solver_key,
            version=releases[0].version,
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

        job_parent_resource_name = compose_resource_name(*collection_or_resource_ids)

        # 2. list jobs under job_parent_resource_name
        return await self._job_service.list_jobs_by_resource_prefix(
            offset=offset,
            limit=limit,
            job_parent_resource_name_prefix=job_parent_resource_name,
        )

    async def solver_release_history(
        self,
        *,
        solver_key: SolverKeyId,
        offset: NonNegativeInt,
        limit: PositiveInt,
    ) -> tuple[list[Solver], PageMetaInfoLimitOffset]:

        releases, page_meta = (
            await self._catalog_service.list_release_history_latest_first(
                service_key=solver_key,
                offset=offset,
                limit=limit,
            )
        )

        service_instance = await self._catalog_service.get(
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

    async def latest_solvers(
        self,
        *,
        offset: NonNegativeInt,
        limit: PositiveInt,
    ) -> tuple[list[Solver], PageMetaInfoLimitOffset]:
        """Lists the latest solvers with pagination."""
        services, page_meta = await self._catalog_service.list_latest_releases(
            offset=offset,
            limit=limit,
            filters=ServiceListFilters(service_type=ServiceType.COMPUTATIONAL),
        )

        solvers = [Solver.create_from_service(service) for service in services]
        return solvers, page_meta
