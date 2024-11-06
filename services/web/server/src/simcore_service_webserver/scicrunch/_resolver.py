"""
    Layer to interact withscicrunch service resolver API
    SEE https://scicrunch.org/resolver

"""

import logging
from datetime import datetime
from typing import Any

from aiohttp import ClientSession
from pydantic import Field, ValidationError
from pydantic.main import BaseModel
from pydantic.types import NonNegativeInt

from .settings import SciCrunchSettings

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

    def flatten_dict(self) -> dict[str, Any]:
        """Used as an output"""
        return {**self.item.model_dump(), **self.rrid.model_dump()}


class HitDetail(BaseModel):
    source: HitSource = Field(..., alias="_source")


class Hits(BaseModel):
    total: NonNegativeInt
    hits: list[HitDetail]


class ResolverInfo(BaseModel):
    uri: str
    timestamp: datetime


class ResolverResponseBody(BaseModel):
    hits: Hits
    resolver: ResolverInfo


class ResolvedItem(BaseModel):
    """Result model for resolve_rrid"""

    description: str
    name: str
    identifier: str
    is_unique: bool
    proper_citation: str


# REQUESTS --------------------------------


async def resolve_rrid(
    identifier: str,
    client: ClientSession,
    settings: SciCrunchSettings,
) -> list[ResolvedItem]:
    """
    API to access to results of https://scicrunch.org/resolver

    """
    # Example https://scicrunch.org/resolver/RRID:AB_90755.json
    identifier = identifier.strip()
    url = f"{settings.SCICRUNCH_RESOLVER_BASE_URL}/{identifier}.json"

    async with client.get(url, raise_for_status=True) as resp:
        body = await resp.json()

    # process and simplify response
    resolved = ResolverResponseBody.model_validate(body)
    if resolved.hits.total == 0:
        return []

    #  WARNING: Not sure why the same RRID can have multiple hits.
    #  We have experience that the order of hits is not preserve and
    #  therefore selecting the first hit is not the right way to go ...
    #
    #  WARNING: scicrunch API has been changing:
    #  - Since Sep.2021, hits returned by resolver DOES NOT guarantee order.
    #  For instance, https://scicrunch.org/resolver/RRID:CVCL_0033.json changes
    #  the order every call and the first hit flips between
    #  '(BCRJ Cat# 0226, RRID:CVCL_0033)' and '(ATCC Cat# HTB-30, RRID:CVCL_0033)'
    #  - Since Dec.2022 hits returned by https://scicrunch.org/resolver/RRID:AB_90755.json
    #  also changed order '(Sigma-Aldrich Cat# AB1542, RRID:AB_90755)' and
    #  '(Millipore Cat# AB1542, RRID:AB_90755)'. Decided to return all hits.
    #
    items = []
    for hit in resolved.hits.hits:
        try:
            items.append(ResolvedItem.model_validate(hit.source.flatten_dict()))
        except ValidationError as err:
            logger.warning("Skipping unexpected response %s: %s", url, err)

    return items
