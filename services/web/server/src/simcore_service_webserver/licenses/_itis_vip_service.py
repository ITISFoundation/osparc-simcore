import logging
from typing import Annotated

import httpx
from pydantic import BaseModel, Field, HttpUrl, ValidationError
from tenacity import (
    retry,
    retry_if_exception_cause_type,
    stop_after_attempt,
    wait_exponential,
)

from ._itis_vip_models import ItisVipData

_logger = logging.getLogger(__name__)


class _ItisVipApiResponse(BaseModel):
    msg: int | None = None  # still not used
    available_downloads: Annotated[list[dict], Field(alias="availableDownloads")]


@retry(
    wait=wait_exponential(multiplier=1, min=4, max=10),
    stop=stop_after_attempt(5),
    retry=retry_if_exception_cause_type(httpx.RequestError),
)
async def get_category_items(
    client: httpx.AsyncClient, url: HttpUrl
) -> list[ItisVipData]:
    """

    Raises:
        httpx.HTTPStatusError
        pydantic.ValidationError
    """
    response = await client.post(f"{url}")
    response.raise_for_status()

    data = _ItisVipApiResponse.model_validate(response.json())

    # Filters only downloads with ItisVipData guarantees
    category_items = []
    for download in data.available_downloads:
        try:
            category_items.append(ItisVipData.model_validate(download))
        except ValidationError as err:
            _logger.debug("Skipped %s because %s", download, err)

    return category_items
