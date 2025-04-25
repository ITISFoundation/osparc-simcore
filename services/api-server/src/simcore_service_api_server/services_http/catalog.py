import logging
import urllib.parse
from dataclasses import dataclass
from functools import partial
from typing import Final, Literal

from fastapi import FastAPI, status
from models_library.emails import LowerCaseEmailStr
from models_library.products import ProductName
from models_library.services import ServiceMetaDataPublished
from models_library.users import UserID
from pydantic import ConfigDict, TypeAdapter
from settings_library.catalog import CatalogSettings
from settings_library.tracing import TracingSettings

from ..exceptions.backend_errors import (
    ProgramOrSolverOrStudyNotFoundError,
)
from ..exceptions.service_errors_utils import service_exception_mapper
from ..models.basic_types import VersionStr
from ..models.schemas.programs import Program
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

    def to_program(self) -> Program:
        data = self.model_dump(
            include={"name", "key", "version", "description", "contact", "owner"},
        )
        return Program(
            id=data.pop("key"),
            version=data.pop("version"),
            title=data.pop("name"),
            url=None,
            **data,
        )


ServiceTypes = Literal["COMPUTATIONAL", "DYNAMIC"]

# API CLASS ---------------------------------------------
#
# - Error handling: What do we reraise, suppress, transform???
#

_exception_mapper = partial(service_exception_mapper, service_name="Catalog")

TruncatedCatalogServiceOutAdapter: Final[TypeAdapter[TruncatedCatalogServiceOut]] = (
    TypeAdapter(TruncatedCatalogServiceOut)
)
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

    @_exception_mapper(
        http_status_map={status.HTTP_404_NOT_FOUND: ProgramOrSolverOrStudyNotFoundError}
    )
    async def get_service_ports(
        self,
        *,
        user_id: UserID,
        name: SolverKeyId,
        version: VersionStr,
        product_name: ProductName,
    ) -> list[SolverPort]:

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
