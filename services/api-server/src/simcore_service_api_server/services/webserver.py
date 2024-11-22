# pylint: disable=too-many-public-methods

import logging
import urllib.parse
from dataclasses import dataclass
from functools import partial
from typing import Any, Mapping
from uuid import UUID

import httpx
from cryptography import fernet
from fastapi import FastAPI, status
from models_library.api_schemas_api_server.pricing_plans import ServicePricingPlanGet
from models_library.api_schemas_long_running_tasks.tasks import TaskGet
from models_library.api_schemas_webserver.computations import ComputationStart
from models_library.api_schemas_webserver.product import GetCreditPrice
from models_library.api_schemas_webserver.projects import (
    ProjectCreateNew,
    ProjectGet,
    ProjectPatch,
)
from models_library.api_schemas_webserver.projects_metadata import (
    ProjectMetadataGet,
    ProjectMetadataUpdate,
)
from models_library.api_schemas_webserver.projects_nodes import NodeOutputs
from models_library.api_schemas_webserver.projects_ports import (
    ProjectInputGet,
    ProjectInputUpdate,
)
from models_library.api_schemas_webserver.resource_usage import (
    PricingPlanGet,
    PricingUnitGet,
)
from models_library.api_schemas_webserver.wallets import (
    WalletGet,
    WalletGetWithAvailableCredits,
)
from models_library.clusters import ClusterID
from models_library.generics import Envelope
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.rest_pagination import Page
from models_library.utils.fastapi_encoders import jsonable_encoder
from pydantic import PositiveInt
from servicelib.aiohttp.long_running_tasks.server import TaskStatus
from servicelib.common_headers import (
    X_SIMCORE_PARENT_NODE_ID,
    X_SIMCORE_PARENT_PROJECT_UUID,
)
from settings_library.tracing import TracingSettings
from simcore_service_api_server.exceptions.backend_errors import (
    ConfigurationError,
    ForbiddenWalletError,
    ListJobsError,
    PaymentRequiredError,
    PricingPlanNotFoundError,
    PricingUnitNotFoundError,
    ProductPriceNotFoundError,
    ProfileNotFoundError,
    ProjectAlreadyStartedError,
    ProjectMetadataNotFoundError,
    ProjectPortsNotFoundError,
    SolverOutputNotFoundError,
    WalletNotFoundError,
)
from tenacity import TryAgain
from tenacity.asyncio import AsyncRetrying
from tenacity.before_sleep import before_sleep_log
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

from ..core.settings import WebServerSettings
from ..exceptions.backend_errors import ClusterNotFoundError, JobNotFoundError
from ..exceptions.service_errors_utils import (
    service_exception_handler,
    service_exception_mapper,
)
from ..models.basic_types import VersionStr
from ..models.pagination import MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE
from ..models.schemas.jobs import MetaValueType
from ..models.schemas.profiles import Profile, ProfileUpdate
from ..models.schemas.solvers import SolverKeyId
from ..models.schemas.studies import StudyPort
from ..utils.client_base import BaseServiceClientApi, setup_client_instance

_logger = logging.getLogger(__name__)

_exception_mapper = partial(service_exception_mapper, "Webserver")

_JOB_STATUS_MAP = {
    status.HTTP_402_PAYMENT_REQUIRED: PaymentRequiredError,
    status.HTTP_404_NOT_FOUND: JobNotFoundError,
}

_PROFILE_STATUS_MAP = {status.HTTP_404_NOT_FOUND: ProfileNotFoundError}

_WALLET_STATUS_MAP = {
    status.HTTP_404_NOT_FOUND: WalletNotFoundError,
    status.HTTP_403_FORBIDDEN: ForbiddenWalletError,
}


def _get_lrt_urls(lrt_response: httpx.Response):
    # WARNING: this function is patched in patch_lrt_response_urls fixture
    data = Envelope[TaskGet].model_validate_json(lrt_response.text).data
    assert data is not None  # nosec

    return data.status_href, data.result_href


class WebserverApi(BaseServiceClientApi):
    """Access to web-server API

    - BaseServiceClientApi:
        - wraps a httpx client
        - lifetime attached to app
        - responsive tests (i.e. ping) to API in-place

    """


class LongRunningTasksClient(BaseServiceClientApi):
    "Client for requesting status and results of long running tasks"


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
    _long_running_task_client: LongRunningTasksClient
    vtag: str
    session_cookies: dict | None = None

    @classmethod
    def create(
        cls,
        app: FastAPI,
        session_cookies: dict,
        product_extra_headers: Mapping[str, str],
    ) -> "AuthSession":
        api = WebserverApi.get_instance(app)
        assert api  # nosec
        assert isinstance(api, WebserverApi)  # nosec

        api.client.headers = product_extra_headers  # type: ignore[assignment]
        long_running_tasks_client = LongRunningTasksClient.get_instance(app=app)

        assert long_running_tasks_client  # nosec
        assert isinstance(long_running_tasks_client, LongRunningTasksClient)  # nosec

        long_running_tasks_client.client.headers = product_extra_headers  # type: ignore[assignment]
        return cls(
            _api=api,
            _long_running_task_client=long_running_tasks_client,
            vtag=app.state.settings.API_SERVER_WEBSERVER.WEBSERVER_VTAG,
            session_cookies=session_cookies,
        )

    # OPERATIONS

    @property
    def client(self):
        return self._api.client

    @property
    def long_running_task_client(self):
        return self._long_running_task_client.client

    async def _page_projects(
        self,
        *,
        limit: int,
        offset: int,
        show_hidden: bool,
        search: str | None = None,
    ) -> Page[ProjectGet]:
        assert 1 <= limit <= MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE  # nosec
        assert offset >= 0  # nosec

        optional: dict[str, Any] = {}
        if search is not None:
            optional["search"] = search

        with service_exception_handler(
            service_name="Webserver",
            http_status_map={status.HTTP_404_NOT_FOUND: ListJobsError},
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

            return Page[ProjectGet].model_validate_json(resp.text)

    async def _wait_for_long_running_task_results(self, lrt_response: httpx.Response):
        status_url, result_url = _get_lrt_urls(lrt_response)

        # GET task status now until done
        async for attempt in AsyncRetrying(
            wait=wait_fixed(0.5),
            stop=stop_after_delay(60),
            reraise=True,
            before_sleep=before_sleep_log(_logger, logging.INFO),
        ):
            with attempt:
                get_response = await self.long_running_task_client.get(
                    url=status_url, cookies=self.session_cookies
                )
                get_response.raise_for_status()
                task_status = (
                    Envelope[TaskStatus].model_validate_json(get_response.text).data
                )
                assert task_status is not None  # nosec
                if not task_status.done:
                    msg = "Timed out creating project. TIP: Try again, or contact oSparc support if this is happening repeatedly"
                    raise TryAgain(msg)

        result_response = await self.long_running_task_client.get(
            f"{result_url}", cookies=self.session_cookies
        )
        result_response.raise_for_status()
        return Envelope.model_validate_json(result_response.text).data

    # PROFILE --------------------------------------------------

    @_exception_mapper(_PROFILE_STATUS_MAP)
    async def get_me(self) -> Profile:
        response = await self.client.get("/me", cookies=self.session_cookies)
        response.raise_for_status()
        profile: Profile | None = (
            Envelope[Profile].model_validate_json(response.text).data
        )
        assert profile is not None  # nosec
        return profile

    @_exception_mapper(_PROFILE_STATUS_MAP)
    async def update_me(self, *, profile_update: ProfileUpdate) -> Profile:
        response = await self.client.put(
            "/me",
            json=profile_update.model_dump(exclude_none=True),
            cookies=self.session_cookies,
        )
        response.raise_for_status()
        profile: Profile = await self.get_me()
        return profile

    # PROJECTS -------------------------------------------------

    @_exception_mapper({})
    async def create_project(
        self,
        project: ProjectCreateNew,
        *,
        is_hidden: bool,
        parent_project_uuid: ProjectID | None,
        parent_node_id: NodeID | None,
    ) -> ProjectGet:
        # POST /projects --> 202 Accepted
        _headers = {
            X_SIMCORE_PARENT_PROJECT_UUID: parent_project_uuid,
            X_SIMCORE_PARENT_NODE_ID: parent_node_id,
        }
        response = await self.client.post(
            "/projects",
            params={"hidden": is_hidden},
            headers={k: f"{v}" for k, v in _headers.items() if v is not None},
            json=jsonable_encoder(project, by_alias=True, exclude={"state"}),
            cookies=self.session_cookies,
        )
        response.raise_for_status()
        result = await self._wait_for_long_running_task_results(response)
        return ProjectGet.model_validate(result)

    @_exception_mapper(_JOB_STATUS_MAP)
    async def clone_project(
        self,
        *,
        project_id: UUID,
        hidden: bool,
        parent_project_uuid: ProjectID | None,
        parent_node_id: NodeID | None,
    ) -> ProjectGet:
        query = {"from_study": project_id, "hidden": hidden}
        _headers = {
            X_SIMCORE_PARENT_PROJECT_UUID: parent_project_uuid,
            X_SIMCORE_PARENT_NODE_ID: parent_node_id,
        }

        response = await self.client.post(
            "/projects",
            cookies=self.session_cookies,
            params=query,
            headers={k: f"{v}" for k, v in _headers.items() if v is not None},
        )
        response.raise_for_status()
        result = await self._wait_for_long_running_task_results(response)
        return ProjectGet.model_validate(result)

    @_exception_mapper(_JOB_STATUS_MAP)
    async def get_project(self, *, project_id: UUID) -> ProjectGet:
        response = await self.client.get(
            f"/projects/{project_id}",
            cookies=self.session_cookies,
        )
        response.raise_for_status()
        data = Envelope[ProjectGet].model_validate_json(response.text).data
        assert data is not None  # nosec
        return data

    async def get_projects_w_solver_page(
        self, *, solver_name: str, limit: int, offset: int
    ) -> Page[ProjectGet]:
        return await self._page_projects(
            limit=limit,
            offset=offset,
            show_hidden=True,
            # WARNING: better way to match jobs with projects (Next PR if this works fine!)
            # WARNING: search text has a limit that I needed to increase for the example!
            search=urllib.parse.quote(solver_name, safe=""),
        )

    async def get_projects_page(self, *, limit: int, offset: int):
        return await self._page_projects(
            limit=limit,
            offset=offset,
            show_hidden=False,
        )

    @_exception_mapper(_JOB_STATUS_MAP)
    async def delete_project(self, *, project_id: ProjectID) -> None:
        response = await self.client.delete(
            f"/projects/{project_id}",
            cookies=self.session_cookies,
        )
        response.raise_for_status()

    @_exception_mapper({status.HTTP_404_NOT_FOUND: ProjectPortsNotFoundError})
    async def get_project_metadata_ports(
        self, *, project_id: ProjectID
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
        data = Envelope[list[StudyPort]].model_validate_json(response.text).data
        assert data is not None  # nosec
        assert isinstance(data, list)  # nosec
        return data

    @_exception_mapper({status.HTTP_404_NOT_FOUND: ProjectMetadataNotFoundError})
    async def get_project_metadata(
        self, *, project_id: ProjectID
    ) -> ProjectMetadataGet:
        response = await self.client.get(
            f"/projects/{project_id}/metadata",
            cookies=self.session_cookies,
        )
        response.raise_for_status()
        data = Envelope[ProjectMetadataGet].model_validate_json(response.text).data
        assert data is not None  # nosec
        return data

    @_exception_mapper(_JOB_STATUS_MAP)
    async def patch_project(self, *, project_id: UUID, patch_params: ProjectPatch):
        response = await self.client.patch(
            f"/projects/{project_id}",
            cookies=self.session_cookies,
            json=jsonable_encoder(patch_params, exclude_unset=True),
        )
        response.raise_for_status()

    @_exception_mapper({status.HTTP_404_NOT_FOUND: ProjectMetadataNotFoundError})
    async def update_project_metadata(
        self, *, project_id: ProjectID, metadata: dict[str, MetaValueType]
    ) -> ProjectMetadataGet:
        response = await self.client.patch(
            f"/projects/{project_id}/metadata",
            cookies=self.session_cookies,
            json=jsonable_encoder(ProjectMetadataUpdate(custom=metadata)),
        )
        response.raise_for_status()
        data = Envelope[ProjectMetadataGet].model_validate_json(response.text).data
        assert data is not None  # nosec
        return data

    @_exception_mapper({status.HTTP_404_NOT_FOUND: PricingUnitNotFoundError})
    async def get_project_node_pricing_unit(
        self, *, project_id: UUID, node_id: UUID
    ) -> PricingUnitGet:
        response = await self.client.get(
            f"/projects/{project_id}/nodes/{node_id}/pricing-unit",
            cookies=self.session_cookies,
        )

        response.raise_for_status()
        data = Envelope[PricingUnitGet].model_validate_json(response.text).data
        assert data is not None  # nosec
        return data

    @_exception_mapper({status.HTTP_404_NOT_FOUND: PricingUnitNotFoundError})
    async def connect_pricing_unit_to_project_node(
        self,
        *,
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

    @_exception_mapper(
        _JOB_STATUS_MAP
        | {
            status.HTTP_409_CONFLICT: ProjectAlreadyStartedError,
            status.HTTP_406_NOT_ACCEPTABLE: ClusterNotFoundError,
            status.HTTP_422_UNPROCESSABLE_ENTITY: ConfigurationError,
        }
    )
    async def start_project(
        self, *, project_id: UUID, cluster_id: ClusterID | None = None
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

    @_exception_mapper({})
    async def update_project_inputs(
        self,
        *,
        project_id: ProjectID,
        new_inputs: list[ProjectInputUpdate],
    ) -> dict[NodeID, ProjectInputGet]:
        response = await self.client.patch(
            f"/projects/{project_id}/inputs",
            cookies=self.session_cookies,
            json=jsonable_encoder(new_inputs),
        )
        response.raise_for_status()
        data: dict[NodeID, ProjectInputGet] | None = (
            Envelope[dict[NodeID, ProjectInputGet]]
            .model_validate_json(response.text)
            .data
        )
        assert data is not None  # nosec
        return data

    @_exception_mapper({})
    async def get_project_inputs(
        self, *, project_id: ProjectID
    ) -> dict[NodeID, ProjectInputGet]:
        response = await self.client.get(
            f"/projects/{project_id}/inputs",
            cookies=self.session_cookies,
        )

        response.raise_for_status()

        data: dict[NodeID, ProjectInputGet] | None = (
            Envelope[dict[NodeID, ProjectInputGet]]
            .model_validate_json(response.text)
            .data
        )
        assert data is not None  # nosec
        return data

    @_exception_mapper({status.HTTP_404_NOT_FOUND: SolverOutputNotFoundError})
    async def get_project_outputs(
        self, *, project_id: ProjectID
    ) -> dict[NodeID, dict[str, Any]]:
        response = await self.client.get(
            f"/projects/{project_id}/outputs",
            cookies=self.session_cookies,
        )

        response.raise_for_status()

        data: dict[NodeID, dict[str, Any]] | None = (
            Envelope[dict[NodeID, dict[str, Any]]]
            .model_validate_json(response.text)
            .data
        )
        assert data is not None  # nosec
        return data

    @_exception_mapper({})
    async def update_node_outputs(
        self, *, project_id: UUID, node_id: UUID, new_node_outputs: NodeOutputs
    ) -> None:
        response = await self.client.patch(
            f"/projects/{project_id}/nodes/{node_id}/outputs",
            cookies=self.session_cookies,
            json=jsonable_encoder(new_node_outputs),
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
        data = (
            Envelope[WalletGetWithAvailableCredits]
            .model_validate_json(response.text)
            .data
        )
        assert data is not None  # nosec
        return data

    @_exception_mapper(_WALLET_STATUS_MAP)
    async def get_wallet(self, *, wallet_id: int) -> WalletGetWithAvailableCredits:
        response = await self.client.get(
            f"/wallets/{wallet_id}",
            cookies=self.session_cookies,
        )
        response.raise_for_status()
        data = (
            Envelope[WalletGetWithAvailableCredits]
            .model_validate_json(response.text)
            .data
        )
        assert data is not None  # nosec
        return data

    @_exception_mapper(_WALLET_STATUS_MAP)
    async def get_project_wallet(self, *, project_id: ProjectID) -> WalletGet:
        response = await self.client.get(
            f"/projects/{project_id}/wallet",
            cookies=self.session_cookies,
        )
        response.raise_for_status()
        data = Envelope[WalletGet].model_validate_json(response.text).data
        assert data is not None  # nosec
        return data

    # PRODUCTS -------------------------------------------------

    @_exception_mapper({status.HTTP_404_NOT_FOUND: ProductPriceNotFoundError})
    async def get_product_price(self) -> GetCreditPrice:
        response = await self.client.get(
            "/credits-price",
            cookies=self.session_cookies,
        )
        response.raise_for_status()
        data = Envelope[GetCreditPrice].model_validate_json(response.text).data
        assert data is not None  # nosec
        return data

    # SERVICES -------------------------------------------------

    @_exception_mapper({status.HTTP_404_NOT_FOUND: PricingPlanNotFoundError})
    async def get_service_pricing_plan(
        self, *, solver_key: SolverKeyId, version: VersionStr
    ) -> ServicePricingPlanGet | None:
        service_key = urllib.parse.quote_plus(solver_key)

        response = await self.client.get(
            f"/catalog/services/{service_key}/{version}/pricing-plan",
            cookies=self.session_cookies,
        )
        response.raise_for_status()
        pricing_plan_get = (
            Envelope[PricingPlanGet].model_validate_json(response.text).data
        )
        if pricing_plan_get:
            return ServicePricingPlanGet.model_construct(
                **pricing_plan_get.model_dump(exclude={"is_active"})
            )
        return None


# MODULES APP SETUP -------------------------------------------------------------


def setup(
    app: FastAPI,
    webserver_settings: WebServerSettings,
    tracing_settings: TracingSettings | None,
) -> None:

    setup_client_instance(
        app,
        WebserverApi,
        api_baseurl=webserver_settings.api_base_url,
        service_name="webserver",
        tracing_settings=tracing_settings,
    )
    setup_client_instance(
        app,
        LongRunningTasksClient,
        api_baseurl="",
        service_name="long_running_tasks_client",
        tracing_settings=tracing_settings,
    )

    def _on_startup() -> None:
        # normalize & encrypt
        secret_key = webserver_settings.WEBSERVER_SESSION_SECRET_KEY.get_secret_value()
        app.state.webserver_fernet = fernet.Fernet(secret_key)

    async def _on_shutdown() -> None:
        _logger.debug("Webserver closed successfully")

    app.add_event_handler("startup", _on_startup)
    app.add_event_handler("shutdown", _on_shutdown)
