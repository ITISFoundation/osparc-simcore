from models_library.services_types import ServiceRunID
from pydantic import BaseModel, PositiveInt


class LicensedItemCheckoutData(BaseModel):
    number_of_seats: PositiveInt
    service_run_id: ServiceRunID
