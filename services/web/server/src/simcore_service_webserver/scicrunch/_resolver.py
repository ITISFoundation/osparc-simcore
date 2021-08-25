"""
    Layer to interact with with scicrunch service resolver API (SEE https://scicrunch.org/resolver)

    - http client for API requests
    - Error handling:
        - translates network errors
        - translates request error codes

"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from aiohttp import ClientSession
from pydantic import Field
from pydantic.main import BaseModel
from pydantic.types import NonNegativeInt
from yarl import URL

from ._config import SciCrunchSettings

logger = logging.getLogger(__name__)


# MODELS ---------------------------

# This is a partial model from the resolver response
# that extracts the information we are interested
# NOTE: this model was deduced by trial-and-error
#
class ItemInfo(BaseModel):
    description: str = ""
    name: str
    identifier: str


class RRIDInfo(BaseModel):
    is_unique: bool = True
    proper_citation: str = Field(..., alias="properCitation")


class HitSource(BaseModel):
    item: ItemInfo
    rrid: RRIDInfo

    def flatten_dict(self) -> Dict[str, Any]:
        """Used as an output"""
        return {**self.item.dict(), **self.rrid.dict()}


class HitDetail(BaseModel):
    source: HitSource = Field(..., alias="_source")


class Hits(BaseModel):
    total: NonNegativeInt
    hits: List[HitDetail]


class ResolverInfo(BaseModel):
    uri: str
    timestamp: datetime


class ResolverResponseBody(BaseModel):
    hits: Hits
    resolver: ResolverInfo


class ResolvedItem(BaseModel):
    """ Result model for resolve_rrid """

    description: str
    name: str
    identifier: str
    is_unique: bool
    proper_citation: str


# REQUESTS --------------------------------


async def resolve_rrid(
    identifier: str, client: ClientSession, settings: SciCrunchSettings
) -> Optional[ResolvedItem]:
    """
    Provides a API to access to results as provided by this web https://scicrunch.org/resolver

    """
    # Example https://scicrunch.org/resolver/RRID:AB_90755.json
    url = (
        URL(str(settings.api_base_url))
        .origin()
        .with_path(f"/resolver/{identifier.strip()}.json")
    )

    async with client.get(url, raise_for_status=True) as resp:
        body = await resp.json()

    # process and simplify response
    resolved = ResolverResponseBody.parse_obj(body)
    if resolved.hits.total == 0:
        return None

    hit = resolved.hits.hits[0].source

    if resolved.hits.total > 1:
        logger.warning(
            "Multiple hits (%d) for '%s'. Returning first",
            resolved.hits.total,
            identifier,
        )
    else:
        assert resolved.hits.total == 1  # nosec

    output = ResolvedItem.parse_obj(hit.flatten_dict())
    return output
