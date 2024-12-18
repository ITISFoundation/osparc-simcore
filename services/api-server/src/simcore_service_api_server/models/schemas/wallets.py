from models_library.resource_tracker import ServiceRunId
from pydantic import BaseModel


class LicensedItemCheckoutData(BaseModel):
    number_of_seats: int
    service_run_id: ServiceRunId
