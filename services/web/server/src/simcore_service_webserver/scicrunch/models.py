"""
   Domain models at every interface: scicrunch API, pg database and webserver API
"""

import logging
import re
from datetime import datetime

from pydantic import field_validator, ConfigDict, BaseModel, Field

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

STRICT_RRID_PATTERN = (
    r"^(RRID:)([^_\s]{1,30})_(\S{1,30})$"  # Expected in db labels and models
)

RRID_TAG_PATTERN = r"(RRID:)?\s{0,5}([^:_\s]{1,30})_(\S{1,30})"
rrid_capture_re = re.compile(RRID_TAG_PATTERN)


def normalize_rrid_tags(rrid_tag: str, *, with_prefix: bool = True) -> str:
    try:
        # validate & parse
        matched = rrid_capture_re.search(rrid_tag)
        assert matched  # nosec
        _, source_authority, identifier = matched.groups()
        # format according to norm
        rrid = f"{source_authority}_{identifier}"
        if with_prefix:
            rrid = "RRID:" + rrid
        return rrid
    except AttributeError as err:
        msg = f"'{rrid_tag}' does not match a RRID pattern"
        raise ValueError(msg) from err


class ResourceHit(BaseModel):
    rrid: str = Field(..., alias="rid")
    name: str


# webserver API models -----------------------------------------
class ResearchResource(BaseModel):
    rrid: str = Field(
        ...,
        description="Unique identifier used as classifier, i.e. to tag studies and services",
        pattern=STRICT_RRID_PATTERN,
    )
    name: str
    description: str

    @field_validator("rrid", mode="before")
    @classmethod
    def format_rrid(cls, v):
        return normalize_rrid_tags(v, with_prefix=True)
    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)


# postgres_database.scicrunch_resources ORM --------------------
class ResearchResourceAtdB(ResearchResource):
    creation_date: datetime
    last_change_date: datetime
