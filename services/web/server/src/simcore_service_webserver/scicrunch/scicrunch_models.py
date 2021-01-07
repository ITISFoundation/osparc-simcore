"""
   Domain models at every interface: scicrunch API, pg database and webserver API
"""

import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Union

from pydantic import BaseModel, Field, constr, validator
from yarl import URL

logger = logging.getLogger(__name__)


# Research Resource Identifiers --------------------------------
#
# To ensure they are recognizable, unique, and traceable,
# identifiers are prefixed with " RRID:",
# followed by a second tag that indicates the source authority that provided it:
#
#   "AB" for the Antibody Registry,
#   "CVCL" for the Cellosaurus,
#   "MMRRC" for Mutant Mouse Regional Resource Centers,
#   "SCR" for the SciCrunch registry of tools
#
# SEE https://scicrunch.org/resources

STRICT_RRID_PATTERN = r"^(RRID:)([^_\s]+)_(\S+)$"  # Expected in db labels and models

RRID_TAG_PATTERN = r"(RRID:)?\s*([^:_\s]+)_(\S+)"
rrid_capture_re = re.compile(RRID_TAG_PATTERN)


def normalize_rrid_tags(rrid_tag: str, *, with_prefix: bool = True) -> str:
    try:
        # validate & parse
        _, source_authority, identifier = rrid_capture_re.search(rrid_tag).groups()
        # format according to norm
        rrid = f"{source_authority}_{identifier}"
        if with_prefix:
            rrid = "RRID:" + rrid
        return rrid
    except AttributeError:
        raise ValueError(f"'{rrid_tag}' does not match a RRID pattern")


# webserver API models -----------------------------------------
class ResearchResource(BaseModel):
    rrid: constr(regex=STRICT_RRID_PATTERN) = Field(
        ...,
        description="Unique identifier used as classifier, i.e. to tag studies and services",
    )
    name: str
    description: str

    @validator("rrid", pre=True)
    @classmethod
    def format_rrid(cls, v):
        return normalize_rrid_tags(v, with_prefix=True)

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
    value: Union[str, None, List[Any]] = None


class ResourceView(BaseModel):
    resource_fields: List[FieldItem] = Field([], alias="fields")
    version: int
    curation_status: str
    last_curated_version: int
    scicrunch_id: str

    @classmethod
    def from_response_payload(cls, payload: Dict):
        assert payload["success"] == True  # nosec
        return cls(**payload["data"])

    @property
    def is_curated(self) -> bool:
        return self.curation_status.lower() == "curated"

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


class ResourceHit(BaseModel):
    rrid: str = Field(..., alias="rid")
    name: str


class ListOfResourceHits(BaseModel):
    __root__: List[ResourceHit]
