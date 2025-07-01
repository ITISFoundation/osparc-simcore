import logging
from datetime import datetime

from models_library.computations import CollectionRunID
from pydantic import BaseModel, ConfigDict

_logger = logging.getLogger(__name__)


class CompRunCollectionDBGet(BaseModel):
    collection_id: CollectionRunID
    client_generated_id: str
    client_generated_display_name: str
    created: datetime

    model_config = ConfigDict(from_attributes=True)
