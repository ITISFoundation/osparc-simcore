from models_library.resource_tracker import ServiceRunId
from models_library.resource_tracker_licensed_items_checkouts import (
    LicensedItemCheckoutID,
)
from pydantic import BaseModel


class LicensedItemCheckoutData(BaseModel):
    number_of_seats: int
    service_run_id: ServiceRunId


class LicensedItemReleaseData(BaseModel):
    licensed_item_checkout_id: LicensedItemCheckoutID
