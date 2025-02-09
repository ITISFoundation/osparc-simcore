from dataclasses import dataclass
from functools import partial

from fastapi import FastAPI
from models_library.resource_tracker_license_checkouts import LicenseCheckoutID
from servicelib.fastapi.app_state import SingletonInAppStateMixin
from servicelib.rabbitmq._client_rpc import RabbitMQRPCClient
from servicelib.rabbitmq.rpc_interfaces.resource_usage_tracker.errors import (
    LicenseCheckoutNotFoundError as _LicensedItemCheckoutNotFoundError,
)
from servicelib.rabbitmq.rpc_interfaces.resource_usage_tracker.license_checkouts import (
    get_license_checkout as _get_licensed_item_checkout,
)

from ..exceptions.backend_errors import LicensedItemCheckoutNotFoundError
from ..exceptions.service_errors_utils import service_exception_mapper
from ..models.schemas.model_adapter import LicensedItemCheckoutGet

_exception_mapper = partial(
    service_exception_mapper, service_name="ResourceUsageTracker"
)


@dataclass
class ResourceUsageTrackerClient(SingletonInAppStateMixin):
    app_state_name = "resource_usage_tracker_rpc_client"
    _client: RabbitMQRPCClient

    @_exception_mapper(
        rpc_exception_map={
            _LicensedItemCheckoutNotFoundError: LicensedItemCheckoutNotFoundError
        }
    )
    async def get_licensed_item_checkout(
        self, *, product_name: str, licensed_item_checkout_id: LicenseCheckoutID
    ) -> LicensedItemCheckoutGet:
        _licensed_item_checkout = await _get_licensed_item_checkout(
            rabbitmq_rpc_client=self._client,
            product_name=product_name,
            license_checkout_id=licensed_item_checkout_id,
        )
        return LicensedItemCheckoutGet(
            licensed_item_checkout_id=_licensed_item_checkout.license_checkout_id,
            licensed_item_id=_licensed_item_checkout.license_id,
            wallet_id=_licensed_item_checkout.wallet_id,
            user_id=_licensed_item_checkout.user_id,
            product_name=_licensed_item_checkout.product_name,
            started_at=_licensed_item_checkout.started_at,
            stopped_at=_licensed_item_checkout.stopped_at,
            num_of_seats=_licensed_item_checkout.num_of_seats,
        )


def setup(app: FastAPI, rabbitmq_rpc_client: RabbitMQRPCClient):
    resource_usage_tracker_rpc_client = ResourceUsageTrackerClient(
        _client=rabbitmq_rpc_client
    )
    resource_usage_tracker_rpc_client.set_to_app_state(app=app)
