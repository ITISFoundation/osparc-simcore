""" Interface to communicate with the Resource Usage Tracker (RUT)

- httpx client with base_url to PAYMENTS_RESOURCE_USAGE_TRACKER

"""


import contextlib
import logging
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import cast

import httpx
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
from settings_library.resource_usage_tracker import ResourceUsageTrackerSettings

from ..core.settings import ApplicationSettings
from ..utils.base_client_api import BaseHttpApi

_logger = logging.getLogger(__name__)


@dataclass
class ResourceUsageTrackerApi(BaseHttpApi):
    settings: ResourceUsageTrackerSettings

    @classmethod
    def create(cls, settings: ApplicationSettings) -> "ResourceUsageTrackerApi":
        client = httpx.AsyncClient(
            base_url=settings.PAYMENTS_RESOURCE_USAGE_TRACKER.base_url,
        )
        return cls(
            client=client,
            settings=settings.PAYMENTS_RESOURCE_USAGE_TRACKER,
            _exit_stack=contextlib.AsyncExitStack(),
        )

    #
    # app.state
    #

    @classmethod
    def get_from_state(cls, app: FastAPI) -> "ResourceUsageTrackerApi":
        return cast("ResourceUsageTrackerApi", app.state.source_usage_tracker_api)

    @classmethod
    def setup_state(cls, app: FastAPI):
        # create and and save instance in state
        if exists := getattr(app.state, "source_usage_tracker_api", None):
            _logger.warning(
                "Skipping setup. Cannot setup more than once %s: %s",
                ResourceUsageTrackerApi,
                exists,
            )
            return

        app.state.source_usage_tracker_api = api = cls.create(app.state.settings)
        assert cls.get_from_state(app) == api  # nosec

        app.add_event_handler("startup", api.start)
        app.add_event_handler("shutdown", api.close)

    #
    # api
    #

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
        credit_transaction = CreditTransactionCreated.parse_raw(response.text)
        return credit_transaction.credit_transaction_id


def setup_resource_usage_tracker(app: FastAPI):
    assert app.state  # nosec

    ResourceUsageTrackerApi.setup_state(app)
