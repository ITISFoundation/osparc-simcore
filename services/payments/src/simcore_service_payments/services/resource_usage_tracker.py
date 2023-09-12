""" Interface to communicate with the Resource Usage Tracker (RUT)

- httpx client with base_url to PAYMENTS_RESOURCE_USAGE_TRACKER

"""


import logging
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

import httpx
from models_library.api_schemas_resource_usage_tracker.credit_transactions import (
    CreditTransactionCreateBody,
    CreditTransactionCreated,
)
from models_library.products import ProductName
from models_library.resource_tracker import CreditTransactionId
from models_library.users import UserID
from models_library.utils.fastapi_encoders import jsonable_encoder
from models_library.wallets import WalletID
from settings_library.resource_usage_tracker import ResourceUsageTrackerSettings

_logger = logging.getLogger(__name__)


@dataclass
class ResourceUsageTrackerApi:
    client: httpx.AsyncClient
    settings: ResourceUsageTrackerSettings

    # TODO: create a base

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
