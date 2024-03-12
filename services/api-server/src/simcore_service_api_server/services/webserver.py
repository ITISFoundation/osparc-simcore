# pylint: disable=R0904

import logging
import urllib.parse
from dataclasses import dataclass
from functools import partial
from typing import Any, Mapping
from uuid import UUID

from cryptography import fernet
from fastapi import FastAPI
from models_library.api_schemas_long_running_tasks.tasks import TaskGet
from models_library.api_schemas_webserver.computations import ComputationStart
from models_library.api_schemas_webserver.product import GetCreditPrice
from models_library.api_schemas_webserver.projects import ProjectCreateNew, ProjectGet
from models_library.api_schemas_webserver.projects_metadata import (
    ProjectMetadataGet,
    ProjectMetadataUpdate,
)
from models_library.api_schemas_webserver.resource_usage import (
    PricingUnitGet,
    ServicePricingPlanGet,
)
from models_library.api_schemas_webserver.wallets import (
    WalletGet,
    WalletGetWithAvailableCredits,
)
from models_library.basic_types import NonNegativeDecimal
from models_library.clusters import ClusterID
from models_library.generics import Envelope
from models_library.projects import ProjectID
from models_library.rest_pagination import Page
from models_library.utils.fastapi_encoders import jsonable_encoder
from pydantic import PositiveInt
from pydantic.errors import PydanticErrorMixin
from servicelib.aiohttp.long_running_tasks.server import TaskStatus
from simcore_service_api_server.models.schemas.solvers import SolverKeyId
from simcore_service_api_server.models.schemas.studies import StudyPort
from starlette import status
from tenacity import TryAgain
from tenacity._asyncio import AsyncRetrying
from tenacity.before_sleep import before_sleep_log
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

from ..core.settings import WebServerSettings
from ..models.basic_types import VersionStr
from ..models.pagination import MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE
from ..models.schemas.jobs import MetaValueType
from ..models.schemas.profiles import Profile, ProfileUpdate
from ..utils.client_base import BaseServiceClientApi, setup_client_instance
from .service_exception_handling import (
    backend_service_exception_handler,
    service_exception_mapper,
)

_logger = logging.getLogger(__name__)


class WebServerValueError(PydanticErrorMixin, ValueError):
    ...


class ProjectNotFoundError(WebServerValueError):
    code = "webserver.project_not_found"
    msg_template = "Project '{project_id}' not found"


_exception_mapper = partial(service_exception_mapper, "Webserver")

_JOB_STATUS_MAP: Mapping = {
    status.HTTP_402_PAYMENT_REQUIRED: (status.HTTP_402_PAYMENT_REQUIRED, None),
    status.HTTP_404_NOT_FOUND: (
        status.HTTP_404_NOT_FOUND,
        lambda kwargs: f"The job/study {kwargs['project_id']} could not be found",
    ),
}

_PROFILE_STATUS_MAP: Mapping = {
    status.HTTP_404_NOT_FOUND: (
        status.HTTP_404_NOT_FOUND,
        lambda kwargs: "Could not find profile",
    )
}

_WALLET_STATUS_MAP: Mapping = {
    status.HTTP_404_NOT_FOUND: (status.HTTP_404_NOT_FOUND, None),
    status.HTTP_403_FORBIDDEN: (status.HTTP_403_FORBIDDEN, None),
}


class WebserverApi(BaseServiceClientApi):
    """Access to web-server API

    - BaseServiceClientApi:
        - wraps a httpx client
        - lifetime attached to app
        - responsive tests (i.e. ping) to API in-place

    """


@dataclass
class AuthSession:
    """
    - wrapper around thin-client to simplify webserver's API
    - sets endspoint upon construction
    - MIME type: application/json
    - processes responses, returning data or raising formatted HTTP exception
    - The lifetime of an AuthSession is ONE request.

    SEE services/api-server/src/simcore_service_api_server/api/dependencies/webserver.py
    """

    _api: WebserverApi
    vtag: str
    session_cookies: dict | None = None

    @classmethod
    def create(
        cls, app: FastAPI, session_cookies: dict, product_header: dict[str, str]
    ) -> "AuthSession":
        api = WebserverApi.get_instance(app)
        assert api  # nosec
        assert isinstance(api, WebserverApi)  # nosec
        api.client.headers = product_header
        return cls(
            _api=api,
            vtag=app.state.settings.API_SERVER_WEBSERVER.WEBSERVER_VTAG,
            session_cookies=session_cookies,
        )

    # OPERATIONS

    @property
    def client(self):
        return self._api.client

    async def _page_projects(
        self, *, limit: int, offset: int, show_hidden: bool, search: str | None = None
    ):
        assert 1 <= limit <= MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE  # nosec
        assert offset >= 0  # nosec

        optional: dict[str, Any] = {}
        if search is not None:
            optional["search"] = search

        with backend_service_exception_handler(
            "Webserver",
            {
                status.HTTP_404_NOT_FOUND: (
                    status.HTTP_404_NOT_FOUND,
                    lambda kwargs: "Could not list jobs",
                )
            },
        ):
            resp = await self.client.get(
                "/projects",
                params={
                    "type": "user",
                    "show_hidden": show_hidden,
                    "limit": limit,
                    "offset": offset,
                    **optional,
                },
                cookies=self.session_cookies,
            )
            resp.raise_for_status()

            return Page[ProjectGet].parse_raw(resp.text)

    async def _wait_for_long_running_task_results(self, data: TaskGet):
        # NOTE: /v0 is already included in the http client base_url
        status_url = data.status_href.lstrip(f"/{self.vtag}")
        result_url = data.result_href.lstrip(f"/{self.vtag}")

        # GET task status now until done
        async for attempt in AsyncRetrying(
            wait=wait_fixed(0.5),
            stop=stop_after_delay(60),
            reraise=True,
            before_sleep=before_sleep_log(_logger, logging.INFO),
        ):
            with attempt:
                get_response = await self.client.get(
                    status_url, cookies=self.session_cookies
                )
                get_response.raise_for_status()
                task_status = Envelope[TaskStatus].parse_raw(get_response.text).data
                assert task_status is not None
                if not task_status.done:
                    msg = "Timed out creating project. TIP: Try again, or contact oSparc support if this is happening repeatedly"
                    raise TryAgain(msg)

        result_response = await self.client.get(
            f"{result_url}", cookies=self.session_cookies
        )
        result_response.raise_for_status()
        return Envelope.parse_raw(result_response.text).data

    # PROFILE --------------------------------------------------

    @_exception_mapper(_PROFILE_STATUS_MAP)
    async def get_me(self) -> Profile:
        response = await self.client.get("/me", cookies=self.session_cookies)
        response.raise_for_status()
        profile: Profile | None = Envelope[Profile].parse_raw(response.text).data
        assert profile is not None
        return profile

    @_exception_mapper(_PROFILE_STATUS_MAP)
    async def update_me(self, profile_update: ProfileUpdate) -> Profile:
        response = await self.client.put(
            "/me",
            json=profile_update.dict(exclude_none=True),
            cookies=self.session_cookies,
        )
        response.raise_for_status()
        profile: Profile = await self.get_me()
        return profile

    # PROJECTS -------------------------------------------------

    @_exception_mapper({})
    async def create_project(self, project: ProjectCreateNew) -> ProjectGet:
        # POST /projects --> 202 Accepted
        response = await self.client.post(
            "/projects",
            params={"hidden": True},
            json=jsonable_encoder(project, by_alias=True, exclude={"state"}),
            cookies=self.session_cookies,
        )
        response.raise_for_status()
        data = Envelope[TaskGet].parse_raw(response.text).data
        assert data is not None  # nosec

        result = await self._wait_for_long_running_task_results(data)
        return ProjectGet.parse_obj(result)

    @_exception_mapper(_JOB_STATUS_MAP)
    async def clone_project(self, project_id: UUID) -> ProjectGet:
        response = await self.client.post(
            f"/projects/{project_id}:clone",
            cookies=self.session_cookies,
        )
        response.raise_for_status()
        data = Envelope[TaskGet].parse_raw(response.text).data
        assert data is not None  # nosec

        result = await self._wait_for_long_running_task_results(data)
        return ProjectGet.parse_obj(result)

    @_exception_mapper(_JOB_STATUS_MAP)
    async def get_project(self, project_id: UUID) -> ProjectGet:
        response = await self.client.get(
            f"/projects/{project_id}",
            cookies=self.session_cookies,
        )
        response.raise_for_status()
        data = Envelope[ProjectGet].parse_raw(response.text).data
        assert data is not None
        return data

    async def get_projects_w_solver_page(
        self, solver_name: str, limit: int, offset: int
    ) -> Page[ProjectGet]:
        return await self._page_projects(
            limit=limit,
            offset=offset,
            show_hidden=True,
            # WARNING: better way to match jobs with projects (Next PR if this works fine!)
            # WARNING: search text has a limit that I needed to increase for the example!
            search=urllib.parse.quote(solver_name, safe=""),
        )

    async def get_projects_page(self, limit: int, offset: int):
        return await self._page_projects(
            limit=limit,
            offset=offset,
            show_hidden=False,
        )

    @_exception_mapper(_JOB_STATUS_MAP)
    async def delete_project(self, project_id: ProjectID) -> None:
        response = await self.client.delete(
            f"/projects/{project_id}",
            cookies=self.session_cookies,
        )
        response.raise_for_status()

    @_exception_mapper(
        {
            status.HTTP_404_NOT_FOUND: (
                status.HTTP_404_NOT_FOUND,
                lambda kwargs: f"The ports for the job/study {kwargs['project_id']} could not be found",
            )
        }
    )
    async def get_project_metadata_ports(
        self, project_id: ProjectID
    ) -> list[StudyPort]:
        """
        maps GET "/projects/{study_id}/metadata/ports", unenvelopes
        and returns data
        """
        response = await self.client.get(
            f"/projects/{project_id}/metadata/ports",
            cookies=self.session_cookies,
        )
        response.raise_for_status()
        data = Envelope[list[StudyPort]].parse_raw(response.text).data
        assert data is not None
        assert isinstance(data, list)
        return data

    @_exception_mapper(
        {
            status.HTTP_404_NOT_FOUND: (
                status.HTTP_404_NOT_FOUND,
                lambda kwargs: f"The metadata for the job/study {kwargs['project_id']} could not be found",
            )
        }
    )
    async def get_project_metadata(self, project_id: ProjectID) -> ProjectMetadataGet:
        response = await self.client.get(
            f"/projects/{project_id}/metadata",
            cookies=self.session_cookies,
        )
        response.raise_for_status()
        data = Envelope[ProjectMetadataGet].parse_raw(response.text).data
        assert data  # nosec
        return data

    @_exception_mapper(
        {
            status.HTTP_404_NOT_FOUND: (
                status.HTTP_404_NOT_FOUND,
                lambda kwargs: f"The metadata for the job/study {kwargs['project_id']} could not be found",
            )
        }
    )
    async def update_project_metadata(
        self, project_id: ProjectID, metadata: dict[str, MetaValueType]
    ) -> ProjectMetadataGet:
        response = await self.client.patch(
            f"/projects/{project_id}/metadata",
            cookies=self.session_cookies,
            json=jsonable_encoder(ProjectMetadataUpdate(custom=metadata)),
        )
        response.raise_for_status()
        data = Envelope[ProjectMetadataGet].parse_raw(response.text).data
        assert data  # nosec
        return data

    @_exception_mapper({status.HTTP_404_NOT_FOUND: (status.HTTP_404_NOT_FOUND, None)})
    async def get_project_node_pricing_unit(
        self, project_id: UUID, node_id: UUID
    ) -> PricingUnitGet | None:
        response = await self.client.get(
            f"/projects/{project_id}/nodes/{node_id}/pricing-unit",
            cookies=self.session_cookies,
        )

        response.raise_for_status()
        data = Envelope[PricingUnitGet].parse_raw(response.text).data
        return data

    @_exception_mapper({status.HTTP_404_NOT_FOUND: (status.HTTP_404_NOT_FOUND, None)})
    async def connect_pricing_unit_to_project_node(
        self,
        project_id: UUID,
        node_id: UUID,
        pricing_plan: PositiveInt,
        pricing_unit: PositiveInt,
    ) -> None:
        response = await self.client.put(
            f"/projects/{project_id}/nodes/{node_id}/pricing-plan/{pricing_plan}/pricing-unit/{pricing_unit}",
            cookies=self.session_cookies,
        )
        response.raise_for_status()

    @_exception_mapper(_JOB_STATUS_MAP)
    async def start_project(
        self, project_id: UUID, cluster_id: ClusterID | None = None
    ) -> None:
        body_input: dict[str, Any] = {}
        if cluster_id:
            body_input["cluster_id"] = cluster_id
        body: ComputationStart = ComputationStart(**body_input)
        response = await self.client.post(
            f"/computations/{project_id}:start",
            cookies=self.session_cookies,
            json=jsonable_encoder(body, exclude_unset=True, exclude_defaults=True),
        )
        response.raise_for_status()

    # WALLETS -------------------------------------------------

    @_exception_mapper(_WALLET_STATUS_MAP)
    async def get_default_wallet(self) -> WalletGetWithAvailableCredits:
        response = await self.client.get(
            "/wallets/default",
            cookies=self.session_cookies,
        )
        response.raise_for_status()
        data = Envelope[WalletGetWithAvailableCredits].parse_raw(response.text).data
        assert data  # nosec
        return data

    @_exception_mapper(_WALLET_STATUS_MAP)
    async def get_wallet(self, wallet_id: int) -> WalletGetWithAvailableCredits:
        response = await self.client.get(
            f"/wallets/{wallet_id}",
            cookies=self.session_cookies,
        )
        response.raise_for_status()
        data = Envelope[WalletGetWithAvailableCredits].parse_raw(response.text).data
        assert data  # nosec
        return data

    @_exception_mapper(_WALLET_STATUS_MAP)
    async def get_project_wallet(self, project_id: ProjectID) -> WalletGet | None:
        response = await self.client.get(
            f"/projects/{project_id}/wallet",
            cookies=self.session_cookies,
        )
        response.raise_for_status()
        data = Envelope[WalletGet].parse_raw(response.text).data
        return data

    # PRODUCTS -------------------------------------------------

    @_exception_mapper({status.HTTP_404_NOT_FOUND: (status.HTTP_404_NOT_FOUND, None)})
    async def get_product_price(self) -> NonNegativeDecimal | None:
        response = await self.client.get(
            "/credits-price",
            cookies=self.session_cookies,
        )
        response.raise_for_status()
        data = Envelope[GetCreditPrice].parse_raw(response.text).data
        assert data is not None
        return data.usd_per_credit

    # SERVICES -------------------------------------------------

    @_exception_mapper({status.HTTP_404_NOT_FOUND: (status.HTTP_404_NOT_FOUND, None)})
    async def get_service_pricing_plan(
        self, solver_key: SolverKeyId, version: VersionStr
    ) -> ServicePricingPlanGet | None:
        service_key = urllib.parse.quote_plus(solver_key)

        response = await self.client.get(
            f"/catalog/services/{service_key}/{version}/pricing-plan",
            cookies=self.session_cookies,
        )
        response.raise_for_status()
        data = Envelope[ServicePricingPlanGet].parse_raw(response.text).data
        return data


# MODULES APP SETUP -------------------------------------------------------------


def setup(app: FastAPI, settings: WebServerSettings | None = None) -> None:
    if not settings:
        settings = WebServerSettings.create_from_envs()

    assert settings is not None  # nosec

    setup_client_instance(
        app, WebserverApi, api_baseurl=settings.api_base_url, service_name="webserver"
    )

    def _on_startup() -> None:
        # normalize & encrypt
        secret_key = settings.WEBSERVER_SESSION_SECRET_KEY.get_secret_value()
        app.state.webserver_fernet = fernet.Fernet(secret_key)

    async def _on_shutdown() -> None:
        _logger.debug("Webserver closed successfully")

    app.add_event_handler("startup", _on_startup)
    app.add_event_handler("shutdown", _on_shutdown)
