import logging
from datetime import datetime
from typing import Any, NamedTuple, cast

from models_library.basic_types import IDStr
from models_library.licensed_items import (
    VIP_DETAILS_EXAMPLE,
    LicensedItemID,
    LicensedResourceType,
)
from models_library.resource_tracker import PricingPlanId, PricingUnitId
from models_library.resource_tracker_licensed_items_purchases import (
    LicensedItemPurchaseID,
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
from pydantic import BaseModel, ConfigDict, Field, PositiveInt
from pydantic.config import JsonDict
from servicelib.request_keys import RQT_USERID_KEY

from ..._constants import RQ_PRODUCT_KEY

_logger = logging.getLogger(__name__)


class LicensedItem(BaseModel):
    licensed_item_id: LicensedItemID
    display_name: str
    licensed_resource_name: str
    licensed_resource_type: LicensedResourceType
    licensed_resource_data: dict[str, Any]
    pricing_plan_id: PricingPlanId
    created_at: datetime
    modified_at: datetime

    @staticmethod
    def _update_json_schema_extra(schema: JsonDict) -> None:
        schema.update(
            {
                "examples": [
                    {
                        "licensed_item_id": "0362b88b-91f8-4b41-867c-35544ad1f7a1",
                        "display_name": "my best model",
                        "licensed_resource_name": "best-model",
                        "licensed_resource_type": f"{LicensedResourceType.VIP_MODEL}",
                        "licensed_resource_data": cast(JsonDict, VIP_DETAILS_EXAMPLE),
                        "pricing_plan_id": "15",
                        "created_at": "2024-12-12 09:59:26.422140",
                        "modified_at": "2024-12-12 09:59:26.422140",
                    }
                ]
            }
        )

    model_config = ConfigDict(json_schema_extra=_update_json_schema_extra)


class LicensedItemPage(NamedTuple):
    items: list[LicensedItem]
    total: PositiveInt


class LicensedItemsRequestContext(RequestParameters):
    user_id: UserID = Field(..., alias=RQT_USERID_KEY)  # type: ignore[literal-required]
    product_name: str = Field(..., alias=RQ_PRODUCT_KEY)  # type: ignore[literal-required]


class LicensedItemsPathParams(StrictRequestParameters):
    licensed_item_id: LicensedItemID


_LicensedItemsListOrderQueryParams: type[
    RequestParameters
] = create_ordering_query_model_class(
    ordering_fields={
        "display_name",
        "modified_at",
    },
    default=OrderBy(field=IDStr("display_name"), direction=OrderDirection.DESC),
    ordering_fields_api_to_column_map={"modified_at": "modified"},
)


class LicensedItemsListQueryParams(
    PageQueryParameters,
    _LicensedItemsListOrderQueryParams,  # type: ignore[misc, valid-type]
):
    ...


class LicensedItemsBodyParams(BaseModel):
    wallet_id: WalletID
    pricing_plan_id: PricingPlanId
    pricing_unit_id: PricingUnitId
    num_of_seats: int

    model_config = ConfigDict(extra="forbid")


class LicensedItemsPurchasesPathParams(StrictRequestParameters):
    licensed_item_purchase_id: LicensedItemPurchaseID


_LicensedItemsPurchasesListOrderQueryParams: type[
    RequestParameters
] = create_ordering_query_model_class(
    ordering_fields={
        "purchased_at",
        "modified_at",
        "name",
    },
    default=OrderBy(field=IDStr("purchased_at"), direction=OrderDirection.DESC),
    ordering_fields_api_to_column_map={"modified_at": "modified"},
)


class LicensedItemsPurchasesListQueryParams(
    PageQueryParameters,
    _LicensedItemsPurchasesListOrderQueryParams,  # type: ignore[misc, valid-type]
):
    ...
