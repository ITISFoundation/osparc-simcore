"""
   Domain model to exchange data between scicrunch API, pg database and webserver API
"""


import logging
from typing import Any, List, Optional, Union
from uuid import UUID

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# NOTE: there is no need to capture everything
#
# scicrunh API fields = [
#   {
#     "field": "Resource Name",
#     "required": true,
#     "type": "text",
#     "max_number": "1",
#     "value": "Jupyter Notebook",
#     "position": 0,
#     "display": "title",
#     "alt": "The name of the unique resource you are submitting"
#   }, ...
# ]


class FieldItem(BaseModel):
    field_name: str = Field(..., alias="field")
    required: bool
    # field_type: str = Field(..., alias="type") # text, textarea, resource-types, ...
    # max_number: str  # convertable to int
    value: Union[str, None, List[Any]] = None
    # position: int
    # display: str  # title, descripiotn, url, text, owner-text
    alt: str  # alternative text


# NOTE: scicrunch API response to
# {
#   "data": {
#     "fields": [ ... ]
#     "version": 2,
#     "curation_status": "Curated",
#     "last_curated_version": 2,
#     "scicrunch_id": "SCR_018315",
#     "original_id": "SCR_018315",
#     "image_src": null,
#     "uuid": "0e88ffa5-752f-5ae6-aab1-b350edbe2ccc",
#     "typeID": 1
#   },
#   "success": true
# }
class ResourceView(BaseModel):
    resource_fields: Optional[List[FieldItem]] = Field(None, alias="fields")
    # version: int
    curation_status: str
    last_curated_version: int
    uuid: UUID
    # typeID: int
    image_src: Optional[str] = None
    scicrunch_id: str
    # original_id: str

    @property
    def is_curated(self) -> bool:
        return self.curation_status.lower() == "curated"

    # TODO: add validator to capture only selected fields

    def get_name(self) -> Optional[str]:
        for field in self.resource_fields:
            if field.field_name == "Resource Name":
                return field.value
        return None
