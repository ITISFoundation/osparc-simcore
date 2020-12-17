"""
   Domain models at every interface: scicrunch API, pg database and webserver API
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Union

from pydantic import BaseModel, Field, constr, validator
from yarl import URL

from ._config import STRICT_RRID_PATTERN

logger = logging.getLogger(__name__)


# webserver API models -----------------------------------------
class ResearchResource(BaseModel):
    rrid: constr(
        regex=STRICT_RRID_PATTERN
    )  # unique identifier used as classifier, i.e. to tag studies and services
    name: str
    description: str

    @validator("rrid", pre=True)
    @classmethod
    def format_rrid(cls, v):
        if not v.startswith("RRID:"):
            return f"RRID: {v}"
        return v

    class Config:
        orm_mode = True
        anystr_strip_whitespace = True


# postgres_database.scicrunch_resources ORM --------------------
class ResearchResourceAtdB(ResearchResource):
    creation_date: datetime
    last_change_date: datetime


# scrunch service API models -----------------------------------
#
# NOTE: These models are a trucated version of the data payload for a scicrunch response.#
# NOTE: Examples of complete responsens can be found in test_scicrunch.py::mock_scicrunch_service_api
class FieldItem(BaseModel):
    field_name: str = Field(..., alias="field")
    required: bool
    # field_type: str = Field(..., alias="type") # text, textarea, resource-types, ...
    # max_number: str  # convertable to int
    value: Union[str, None, List[Any]] = None
    # position: int
    # display: str  # title, descripiotn, url, text, owner-text
    alt: str  # alternative text


class ResourceView(BaseModel):
    resource_fields: List[FieldItem] = Field([], alias="fields")
    version: int
    curation_status: str
    last_curated_version: int
    # uuid: UUID
    # NOTE: image_src is a path from https://scicrunch.org/ e.g. https://scicrunch.org/upload/resource-images/18997.png
    # image_src: Optional[str]
    scicrunch_id: str

    @classmethod
    def from_response_payload(cls, payload: Dict):
        assert payload["success"] == True  # nosec
        return cls(**payload["data"])

    @property
    def is_curated(self) -> bool:
        return self.curation_status.lower() == "curated"

    # TODO: add validator to capture only selected fields

    def _get_field(self, fieldname: str):
        for field in self.resource_fields:
            if field.field_name == fieldname:
                return field.value
        raise ValueError(f"Cannot file expected field {fieldname}")

    def get_name(self):
        return str(self._get_field("Resource Name"))

    def get_description(self):
        return str(self._get_field("Description"))

    def get_resource_url(self):
        return URL(str(self._get_field("Resource URL")))

    def convert_to_api_model(self) -> ResearchResource:
        return ResearchResource(
            rrid=self.scicrunch_id,
            name=self.get_name(),
            description=self.get_description(),
        )


class ResourceHit(BaseModel):
    rrid: str = Field(..., alias="rid")
    # original_id: str
    name: str


class ListOfResourceHits(BaseModel):
    __root__: List[ResourceHit]
