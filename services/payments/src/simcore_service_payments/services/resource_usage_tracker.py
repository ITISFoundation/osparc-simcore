""" Interface to communicate with the Resource Usage Tracker (RUT)

- httpx client with base_url to PAYMENTS_RESOURCE_USAGE_TRACKER

"""


import logging
from datetime import datetime
from decimal import Decimal

from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from models_library.api_schemas_resource_usage_tracker.credit_transactions import (
    CreditTransactionCreateBody,
    CreditTransactionCreated,
)
from models_library.products import ProductName
from models_library.resource_tracker import CreditTransactionId
from models_library.users import UserID
from models_library.wallets import WalletID
from servicelib.fastapi.app_state import SingletonInAppStateMixin
from servicelib.fastapi.http_client import (
    AttachLifespanMixin,
    BaseHTTPApi,
    HealthMixinMixin,
)
from servicelib.fastapi.tracing import setup_httpx_client_tracing

from ..core.settings import ApplicationSettings

_logger = logging.getLogger(__name__)


class ResourceUsageTrackerApi(
    BaseHTTPApi, AttachLifespanMixin, HealthMixinMixin, SingletonInAppStateMixin
):
    app_state_name: str = "source_usage_tracker_api"

    async def create_credit_transaction(
        self,
        product_name: ProductName,
        wallet_id: WalletID,
        wallet_name: str,
        user_id: UserID,
        user_email: str,
        osparc_credits: Decimal,
        payment_transaction_id: str,
        created_at: datetime,
    ) -> CreditTransactionId:
        """Adds credits to wallet"""
        response = await self.client.post(
            "/v1/credit-transactions",
            json=jsonable_encoder(
                CreditTransactionCreateBody(
                    product_name=product_name,
                    wallet_id=wallet_id,
                    wallet_name=wallet_name,
                    user_id=user_id,
                    user_email=user_email,
                    osparc_credits=osparc_credits,
                    payment_transaction_id=payment_transaction_id,
                    created_at=created_at,
                )
            ),
        )
        credit_transaction = CreditTransactionCreated.model_validate_json(response.text)
        return credit_transaction.credit_transaction_id


def setup_resource_usage_tracker(app: FastAPI):
    assert app.state  # nosec
    settings: ApplicationSettings = app.state.settings
    api = ResourceUsageTrackerApi.from_client_kwargs(
        base_url=settings.PAYMENTS_RESOURCE_USAGE_TRACKER.base_url,
    )
    if settings.PAYMENTS_TRACING:
        setup_httpx_client_tracing(api.client)
    api.set_to_app_state(app)
    api.attach_lifespan_to(app)
