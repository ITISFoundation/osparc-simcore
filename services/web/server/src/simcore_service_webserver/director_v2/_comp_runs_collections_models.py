import logging
from datetime import datetime

from models_library.computations import CollectionRunID
from pydantic import BaseModel, ConfigDict

_logger = logging.getLogger(__name__)


class CompRunCollectionDBGet(BaseModel):
    collection_run_id: CollectionRunID
    client_or_system_generated_id: str
    client_or_system_generated_display_name: str
    generated_by_system: bool
    created: datetime

    model_config = ConfigDict(from_attributes=True)
