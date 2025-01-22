from datetime import datetime
from typing import NamedTuple

from models_library.basic_types import IDStr
from models_library.licensed_items import LicensedItemID
from models_library.products import ProductName
from models_library.resource_tracker_licensed_items_checkouts import (
    LicensedItemCheckoutID,
)
from models_library.rest_base import RequestParameters, StrictRequestParameters
from models_library.rest_ordering import (
    OrderBy,
    OrderDirection,
    create_ordering_query_model_class,
)
from models_library.rest_pagination import PageQueryParameters
from models_library.users import UserID
from models_library.wallets import WalletID
from pydantic import BaseModel, PositiveInt


class LicensedItemCheckoutGet(BaseModel):
    licensed_item_checkout_id: LicensedItemCheckoutID
    licensed_item_id: LicensedItemID
    wallet_id: WalletID
    user_id: UserID
    user_email: str
    product_name: ProductName
    started_at: datetime
    stopped_at: datetime | None
    num_of_seats: int


class LicensedItemCheckoutGetPage(NamedTuple):
    items: list[LicensedItemCheckoutGet]
    total: PositiveInt


class LicensedItemCheckoutPathParams(StrictRequestParameters):
    licensed_item_checkout_id: LicensedItemCheckoutID


_LicensedItemsCheckoutsListOrderQueryParams: type[
    RequestParameters
] = create_ordering_query_model_class(
    ordering_fields={
        "started_at",
    },
    default=OrderBy(field=IDStr("started_at"), direction=OrderDirection.DESC),
)


class LicensedItemsCheckoutsListQueryParams(
    PageQueryParameters,
    _LicensedItemsCheckoutsListOrderQueryParams,  # type: ignore[misc, valid-type]
):
    ...
