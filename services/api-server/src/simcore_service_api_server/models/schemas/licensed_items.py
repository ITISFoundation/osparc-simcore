from models_library.services_types import ServiceRunID
from pydantic import BaseModel


class LicensedItemCheckoutData(BaseModel):
    number_of_seats: int
    service_run_id: ServiceRunID
