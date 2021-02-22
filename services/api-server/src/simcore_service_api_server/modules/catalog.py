import logging
import urllib.parse
from dataclasses import dataclass, field
from operator import attrgetter
from typing import Callable, Dict, List, Optional, Tuple
from uuid import UUID

import httpx
from fastapi import FastAPI
from models_library.services import ServiceDockerData, ServiceType
from pydantic import EmailStr, Extra, ValidationError

from ..core.settings import CatalogSettings
from ..models.schemas.solvers import LATEST_VERSION, Solver, SolverKeyId, VersionStr
from ..utils.client_base import BaseServiceClientApi

## from ..utils.client_decorators import JsonDataType, handle_errors, handle_retry

logger = logging.getLogger(__name__)

# Module's setup logic ---------------------------------------------


def setup(app: FastAPI, settings: CatalogSettings) -> None:
    if not settings:
        settings = CatalogSettings()

    def on_startup() -> None:
        logger.debug("Setup %s at %s...", __name__, settings.base_url)
        CatalogApi.create(
            app,
            client=httpx.AsyncClient(base_url=settings.base_url),
            service_name="catalog",
        )

    async def on_shutdown() -> None:
        client = CatalogApi.get_instance(app)
        if client:
            await client.aclose()
        logger.debug("%s client closed successfully", __name__)

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)


SolverNameVersionPair = Tuple[SolverKeyId, str]


class TruncatedCatalogServiceOut(ServiceDockerData):
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

    owner: Optional[EmailStr]

    class Config:
        extra = Extra.ignore

    # Converters
    def to_solver(self) -> Solver:
        data = self.dict(
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
#
# TODO: handlers should not capture outputs
# @handle_errors("catalog", logger, return_json=True)
# @handle_retry(logger)
# async def get(self, path: str, *args, **kwargs) -> JsonDataType:
#     return await self.client.get(path, *args, **kwargs)


@dataclass
class CatalogApi(BaseServiceClientApi):
    """
    This class acts a proxy of the catalog service
    It abstracts request to the catalog API service
    """

    async def list_solvers(
        self,
        user_id: int,
        predicate: Optional[Callable[[Solver], bool]] = None,
    ) -> List[Solver]:
        resp = await self.client.get(
            "/services",
            params={"user_id": user_id, "details": False},
            headers={"x-simcore-products-name": "osparc"},
        )
        resp.raise_for_status()

        # TODO: move this sorting down to catalog service?
        solvers = []
        for data in resp.json():
            try:
                service = TruncatedCatalogServiceOut.parse_obj(data)
                if service.service_type == ServiceType.COMPUTATIONAL:
                    solver = service.to_solver()
                    if predicate is None or predicate(solver):
                        solvers.append(solver)

            except ValidationError as err:
                # NOTE: For the moment, this is necessary because there are no guarantees
                #       at the image registry. Therefore we exclude and warn
                #       invalid items instead of returning error
                logger.warning(
                    "Skipping invalid service returned by catalog '%s': %s",
                    data,
                    err,
                )
        return solvers

    async def get_solver(
        self, user_id: int, name: SolverKeyId, version: VersionStr
    ) -> Solver:

        assert version != LATEST_VERSION  # nosec

        service_key = urllib.parse.quote_plus(name)
        service_version = version

        resp = await self.client.get(
            f"/services/{service_key}/{service_version}",
            params={"user_id": user_id},
            headers={"x-simcore-products-name": "osparc"},
        )
        resp.raise_for_status()

        service = TruncatedCatalogServiceOut.parse_obj(resp.json())
        assert (
            service.service_type == ServiceType.COMPUTATIONAL
        ), "Expected by SolverName regex"  # nosec

        return service.to_solver()

    async def list_latest_releases(self, user_id: int):
        solvers: List[Solver] = await self.list_solvers(user_id)

        latest_releases = {}
        for solver in solvers:
            latest = latest_releases.setdefault(solver.id, solver)
            if latest.pep404_version < solver.pep404_version:
                latest_releases[solver.id] = solver

        return list(latest_releases.values())

    async def get_latest_release(self, user_id: int, name: SolverKeyId) -> Solver:
        def _this_solver(solver: Solver) -> bool:
            return solver.id == name

        solvers = await self.list_solvers(user_id, _this_solver)

        # raise IndexError if None
        latest = sorted(solvers, key=attrgetter("pep404_version"))[-1]
        return latest
