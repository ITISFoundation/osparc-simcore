import asyncio
import logging
import urllib.parse
from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from operator import attrgetter
from typing import Final

from fastapi import FastAPI, status
from models_library.emails import LowerCaseEmailStr
from models_library.services import ServiceMetaDataPublished, ServiceType
from pydantic import ConfigDict, TypeAdapter, ValidationError
from settings_library.catalog import CatalogSettings
from settings_library.tracing import TracingSettings
from simcore_service_api_server.exceptions.backend_errors import (
    ListSolversOrStudiesError,
    SolverOrStudyNotFoundError,
)

from ..exceptions.service_errors_utils import service_exception_mapper
from ..models.basic_types import VersionStr
from ..models.schemas.solvers import LATEST_VERSION, Solver, SolverKeyId, SolverPort
from ..utils.client_base import BaseServiceClientApi, setup_client_instance

_logger = logging.getLogger(__name__)


SolverNameVersionPair = tuple[SolverKeyId, str]


class TruncatedCatalogServiceOut(ServiceMetaDataPublished):
    """
    This model is used to truncate the response of the catalog, whose schema is
    in services/catalog/src/simcore_service_catalog/models/schemas/services.py::ServiceOut
    and is a superset of ServiceDockerData.

    We do not use directly ServiceDockerData because it will only consume the exact fields
    (it is configured as Extra.forbid). Instead  we inherit from it, override this configuration
    and add an extra field that we want to capture from ServiceOut.

    Ideally the rest of the response is dropped so here it would
    perhaps make more sense to use something like graphql
    that asks only what is needed.
    """

    owner: LowerCaseEmailStr | None = None
    model_config = ConfigDict(extra="ignore")

    # Converters
    def to_solver(self) -> Solver:
        data = self.model_dump(
            include={"name", "key", "version", "description", "contact", "owner"},
        )

        return Solver(
            id=data.pop("key"),
            version=data.pop("version"),
            title=data.pop("name"),
            maintainer=data.pop("owner") or data.pop("contact"),
            url=None,
            **data,
        )


# API CLASS ---------------------------------------------
#
# - Error handling: What do we reraise, suppress, transform???
#

_exception_mapper = partial(service_exception_mapper, "Catalog")

TruncatedCatalogServiceOutAdapter: Final[
    TypeAdapter[TruncatedCatalogServiceOut]
] = TypeAdapter(TruncatedCatalogServiceOut)
TruncatedCatalogServiceOutListAdapter: Final[
    TypeAdapter[list[TruncatedCatalogServiceOut]]
] = TypeAdapter(list[TruncatedCatalogServiceOut])


def _parse_response(type_adapter: TypeAdapter, response):
    return type_adapter.validate_json(response.text)


@dataclass
class CatalogApi(BaseServiceClientApi):
    """
    This class acts a proxy of the catalog service
    It abstracts request to the catalog API service

    SEE osparc-simcore/services/catalog/openapi.json
    """

    @_exception_mapper({status.HTTP_404_NOT_FOUND: ListSolversOrStudiesError})
    async def list_solvers(
        self,
        *,
        user_id: int,
        product_name: str,
        predicate: Callable[[Solver], bool] | None = None,
    ) -> list[Solver]:

        response = await self.client.get(
            "/services",
            params={"user_id": user_id, "details": True},
            headers={"x-simcore-products-name": product_name},
        )
        response.raise_for_status()

        services: list[
            TruncatedCatalogServiceOut
        ] = await asyncio.get_event_loop().run_in_executor(
            None,
            _parse_response,
            TruncatedCatalogServiceOutListAdapter,
            response,
        )
        solvers = []
        for service in services:
            try:
                if service.service_type == ServiceType.COMPUTATIONAL:
                    solver = service.to_solver()
                    if predicate is None or predicate(solver):
                        solvers.append(solver)

            except ValidationError as err:  # noqa: PERF203
                # NOTE: For the moment, this is necessary because there are no guarantees
                #       at the image registry. Therefore we exclude and warn
                #       invalid items instead of returning error
                _logger.warning(
                    "Skipping invalid service returned by catalog '%s': %s",
                    service.model_dump_json(),
                    err,
                )
        return solvers

    @_exception_mapper({status.HTTP_404_NOT_FOUND: SolverOrStudyNotFoundError})
    async def get_service(
        self, *, user_id: int, name: SolverKeyId, version: VersionStr, product_name: str
    ) -> Solver:

        assert version != LATEST_VERSION  # nosec

        service_key = urllib.parse.quote_plus(name)
        service_version = version

        response = await self.client.get(
            f"/services/{service_key}/{service_version}",
            params={"user_id": user_id},
            headers={"x-simcore-products-name": product_name},
        )
        response.raise_for_status()

        service: (
            TruncatedCatalogServiceOut
        ) = await asyncio.get_event_loop().run_in_executor(
            None, _parse_response, TruncatedCatalogServiceOutAdapter, response
        )
        assert (  # nosec
            service.service_type == ServiceType.COMPUTATIONAL
        ), "Expected by SolverName regex"

        solver: Solver = service.to_solver()
        return solver

    @_exception_mapper({status.HTTP_404_NOT_FOUND: SolverOrStudyNotFoundError})
    async def get_service_ports(
        self, *, user_id: int, name: SolverKeyId, version: VersionStr, product_name: str
    ):

        assert version != LATEST_VERSION  # nosec

        service_key = urllib.parse.quote_plus(name)
        service_version = version

        response = await self.client.get(
            f"/services/{service_key}/{service_version}/ports",
            params={"user_id": user_id},
            headers={"x-simcore-products-name": product_name},
        )

        response.raise_for_status()

        return TypeAdapter(list[SolverPort]).validate_python(response.json())

    async def list_latest_releases(
        self, *, user_id: int, product_name: str
    ) -> list[Solver]:
        solvers: list[Solver] = await self.list_solvers(
            user_id=user_id, product_name=product_name
        )

        latest_releases: dict[SolverKeyId, Solver] = {}
        for solver in solvers:
            latest = latest_releases.setdefault(solver.id, solver)
            if latest.pep404_version < solver.pep404_version:
                latest_releases[solver.id] = solver

        return list(latest_releases.values())

    async def list_solver_releases(
        self, *, user_id: int, solver_key: SolverKeyId, product_name: str
    ) -> list[Solver]:
        def _this_solver(solver: Solver) -> bool:
            return solver.id == solver_key

        releases: list[Solver] = await self.list_solvers(
            user_id=user_id, predicate=_this_solver, product_name=product_name
        )
        return releases

    async def get_latest_release(
        self, *, user_id: int, solver_key: SolverKeyId, product_name: str
    ) -> Solver:
        releases = await self.list_solver_releases(
            user_id=user_id, solver_key=solver_key, product_name=product_name
        )

        # raises IndexError if None
        return sorted(releases, key=attrgetter("pep404_version"))[-1]


# MODULES APP SETUP -------------------------------------------------------------


def setup(
    app: FastAPI, settings: CatalogSettings, tracing_settings: TracingSettings | None
) -> None:
    if not settings:
        settings = CatalogSettings()

    setup_client_instance(
        app,
        CatalogApi,
        api_baseurl=settings.api_base_url,
        service_name="catalog",
        tracing_settings=tracing_settings,
    )
