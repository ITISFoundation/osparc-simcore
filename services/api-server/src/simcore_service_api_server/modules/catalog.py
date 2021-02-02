import logging
import urllib.parse
from operator import attrgetter
from typing import Callable, Dict, List, Optional, Tuple
from uuid import UUID

import httpx
from fastapi import FastAPI
from models_library.services import ServiceDockerData, ServiceType
from pydantic import ValidationError

from ..core.settings import CatalogSettings
from ..models.schemas.solvers import LATEST_VERSION, SolverName
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


# API CLASS ---------------------------------------------

SolverNameVersionPair = Tuple[SolverName, str]


class CatalogApi(BaseServiceClientApi):
    """
    This class acts a proxy of the catalog service
    It abstracts request to the catalog API service
    """

    ids_cache_map: Dict[UUID, SolverNameVersionPair]

    # TODO: handlers should not capture outputs
    # @handle_errors("catalog", logger, return_json=True)
    # @handle_retry(logger)
    # async def get(self, path: str, *args, **kwargs) -> JsonDataType:
    #     return await self.client.get(path, *args, **kwargs)

    async def list_solvers(
        self,
        user_id: int,
        predicate: Optional[Callable[[ServiceDockerData], bool]] = None,
    ) -> List[ServiceDockerData]:
        resp = await self.client.get(
            "/services",
            params={"user_id": user_id, "details": False},
            headers={"x-simcore-products-name": "osparc"},
        )
        resp.raise_for_status()

        # TODO: move this sorting down to database?
        solvers = []
        for data in resp.json():
            try:
                service = ServiceDockerData(**data)
                if service.service_type == ServiceType.COMPUTATIONAL:
                    if predicate is None or predicate(service):
                        solvers.append(service)

            except ValidationError as err:
                # NOTE: This is necessary because there are no guarantees
                #       at the image registry. Therefore we exclude and warn
                #       invalid items instead of returning error
                logger.warning(
                    "Skipping invalid service returned by catalog '%s': %s",
                    data,
                    err,
                )
        return solvers

    async def get_solver(
        self, user_id: int, name: SolverName, version: str
    ) -> ServiceDockerData:

        assert version != LATEST_VERSION  # nosec

        service_key = urllib.parse.quote_plus(name)
        service_version = version

        resp = await self.client.get(
            f"/services/{service_key}/{service_version}",
            params={"user_id": user_id},
            headers={"x-simcore-products-name": "osparc"},
        )

        resp.raise_for_status()

        solver = ServiceDockerData(**resp.json())

        return solver

    async def get_latest_solver(
        self, user_id: int, name: SolverName
    ) -> ServiceDockerData:
        def _this_solver(solver: ServiceDockerData) -> bool:
            return solver.key == name

        solvers = await self.list_solvers(user_id, _this_solver)

        # raise IndexError if None
        latest = sorted(solvers, key=attrgetter("pep404_version"))[-1]
        return latest
