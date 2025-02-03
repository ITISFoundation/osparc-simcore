import httpx
from pydantic import HttpUrl
from tenacity import (
    retry,
    retry_if_exception_cause_type,
    stop_after_attempt,
    wait_exponential,
)

from ._itis_vip_models import ItisVipApiResponse, ItisVipData


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

    validated_data = ItisVipApiResponse.model_validate(response.json())

    return validated_data.available_downloads
