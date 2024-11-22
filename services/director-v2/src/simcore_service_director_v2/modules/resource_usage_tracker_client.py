""" Interface to communicate with the resource usage tracker
"""

import contextlib
import logging
from dataclasses import dataclass
from typing import cast

import httpx
from fastapi import FastAPI, status
from models_library.api_schemas_resource_usage_tracker.credit_transactions import (
    WalletTotalCredits,
)
from models_library.api_schemas_resource_usage_tracker.pricing_plans import (
    PricingPlanGet,
    PricingUnitGet,
)
from models_library.products import ProductName
from models_library.resource_tracker import (
    PricingAndHardwareInfoTuple,
    PricingPlanId,
    PricingUnitId,
)
from models_library.services import ServiceKey, ServiceVersion
from models_library.wallets import WalletID
from servicelib.fastapi.tracing import setup_httpx_client_tracing

from ..core.errors import PricingPlanUnitNotFoundError
from ..core.settings import AppSettings

_logger = logging.getLogger(__name__)


@dataclass
class ResourceUsageTrackerClient:
    client: httpx.AsyncClient
    exit_stack: contextlib.AsyncExitStack

    @classmethod
    def create(cls, settings: AppSettings) -> "ResourceUsageTrackerClient":
        client = httpx.AsyncClient(
            base_url=settings.DIRECTOR_V2_RESOURCE_USAGE_TRACKER.api_base_url,
        )
        if settings.DIRECTOR_V2_TRACING:
            setup_httpx_client_tracing(client=client)
        exit_stack = contextlib.AsyncExitStack()

        return cls(client=client, exit_stack=exit_stack)

    async def start(self):
        await self.exit_stack.enter_async_context(self.client)

    async def close(self):
        await self.exit_stack.aclose()

    #
    # service diagnostics
    #
    async def ping(self) -> bool:
        """Check whether server is reachable"""
        try:
            await self.client.get("/")
            return True
        except httpx.RequestError:
            return False

    async def is_healhy(self) -> bool:
        """Service is reachable and ready"""
        try:
            response = await self.client.get("/")
            response.raise_for_status()
            return True
        except httpx.HTTPError:
            return False

    #
    # pricing plans methods
    #

    async def get_default_service_pricing_plan(
        self,
        product_name: ProductName,
        service_key: ServiceKey,
        service_version: ServiceVersion,
    ) -> PricingPlanGet:
        response = await self.client.get(
            f"/services/{service_key}/{service_version}/pricing-plan",
            params={
                "product_name": product_name,
            },
        )
        if response.status_code == status.HTTP_404_NOT_FOUND:
            msg = "No pricing plan defined"
            raise PricingPlanUnitNotFoundError(msg=msg)

        response.raise_for_status()
        return PricingPlanGet.model_validate(response.json())

    async def get_default_pricing_and_hardware_info(
        self,
        product_name: ProductName,
        service_key: ServiceKey,
        service_version: ServiceVersion,
    ) -> PricingAndHardwareInfoTuple:
        service_pricing_plan_get = await self.get_default_service_pricing_plan(
            product_name=product_name,
            service_key=service_key,
            service_version=service_version,
        )
        assert service_pricing_plan_get.pricing_units  # nosec
        for unit in service_pricing_plan_get.pricing_units:
            if unit.default:
                return PricingAndHardwareInfoTuple(
                    service_pricing_plan_get.pricing_plan_id,
                    unit.pricing_unit_id,
                    unit.current_cost_per_unit_id,
                    unit.specific_info.aws_ec2_instances,
                )
        msg = "Default pricing plan and unit does not exist"
        raise PricingPlanUnitNotFoundError(msg=msg)

    async def get_pricing_unit(
        self,
        product_name: ProductName,
        pricing_plan_id: PricingPlanId,
        pricing_unit_id: PricingUnitId,
    ) -> PricingUnitGet:
        response = await self.client.get(
            f"/pricing-plans/{pricing_plan_id}/pricing-units/{pricing_unit_id}",
            params={
                "product_name": product_name,
            },
        )
        response.raise_for_status()
        return PricingUnitGet.model_validate(response.json())

    async def get_wallet_credits(
        self,
        product_name: ProductName,
        wallet_id: WalletID,
    ) -> WalletTotalCredits:
        response = await self.client.post(
            "/credit-transactions/credits:sum",
            params={"product_name": product_name, "wallet_id": wallet_id},
        )
        response.raise_for_status()
        return WalletTotalCredits.model_validate(response.json())

    #
    # app
    #

    @classmethod
    def get_from_state(cls, app: FastAPI) -> "ResourceUsageTrackerClient":
        return cast("ResourceUsageTrackerClient", app.state.resource_usage_api)

    @classmethod
    def setup(cls, app: FastAPI):
        assert app.state  # nosec
        if exists := getattr(app.state, "resource_usage_api", None):
            _logger.warning(
                "Skipping setup. Cannot setup more than once %s: %s", cls, exists
            )
            return

        assert not hasattr(app.state, "resource_usage_api")  # nosec
        app_settings: AppSettings = app.state.settings

        app.state.resource_usage_api = api = cls.create(app_settings)

        async def on_startup():
            await api.start()

        async def on_shutdown():
            await api.close()

        app.add_event_handler("startup", on_startup)
        app.add_event_handler("shutdown", on_shutdown)


def setup(app: FastAPI):
    assert app.state  # nosec
    ResourceUsageTrackerClient.setup(app)
