import contextlib
import logging
from dataclasses import dataclass
from typing import cast

import httpx
from fastapi import FastAPI
from models_library.api_schemas_webserver.resource_usage import PricingPlanGet
from models_library.products import ProductName
from models_library.resource_tracker import PricingDetailId, PricingPlanId
from models_library.services import ServiceKey, ServiceVersion
from pydantic import parse_obj_as

from ..core.settings import AppSettings

""" Interface to communicate with the payment's gateway

- httpx client with base_url to PAYMENTS_GATEWAY_URL
- Fake gateway service in services/payments/scripts/fake_payment_gateway.py

"""


_logger = logging.getLogger(__name__)


@dataclass
class ResourceUsageApi:
    client: httpx.AsyncClient
    exit_stack: contextlib.AsyncExitStack

    @classmethod
    def create(cls, settings: AppSettings) -> "ResourceUsageApi":
        client = httpx.AsyncClient(
            base_url=settings.DIRECTOR_V2_RESOURCE_USAGE_TRACKER.api_base_url,
        )
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

    async def get_pricing_plans_for_service(
        self,
        product_name: ProductName,
        service_key: ServiceKey,
        service_version: ServiceVersion,
    ) -> list[PricingPlanGet]:
        response = await self.client.get(
            "/pricing-plans",
            params={
                "product_name": product_name,
                "service_key": service_key,
                "service_version": service_version,
            },
        )
        response.raise_for_status()
        return parse_obj_as(list[PricingPlanGet], response.json())

    async def get_default_pricing_plan_and_pricing_detail_for_service(
        self,
        product_name: ProductName,
        service_key: ServiceKey,
        service_version: ServiceVersion,
    ) -> tuple[PricingPlanId, PricingDetailId]:
        pricing_plans = await self.get_pricing_plans_for_service(
            product_name, service_key, service_version
        )
        if pricing_plans:
            default_pricing_plan = pricing_plans[0]
            default_pricing_detail = pricing_plans[0].details[0]
            return (
                default_pricing_plan.pricing_plan_id,
                default_pricing_detail.pricing_detail_id,
            )
        raise ValueError(
            f"No default pricing plan provided for requested service key: {service_key} version: {service_version} product: {product_name}"
        )

    #
    # app
    #

    @classmethod
    def get_from_state(cls, app: FastAPI) -> "ResourceUsageApi":
        return cast("ResourceUsageApi", app.state.resource_usage_api)

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
    ResourceUsageApi.setup(app)
