import httpx
from pydantic import HttpUrl

from ._itis_vip_models import AvailableDownload, ResponseData


async def get_category_items(
    client: httpx.AsyncClient, url: HttpUrl
) -> list[AvailableDownload]:
    """

    Raises:
        Any https://www.python-httpx.org/exceptions/
        httpx.HTTPStatusCode:

    """
    response = await client.post(f"{url}")
    response.raise_for_status()
    validated_data = ResponseData.model_validate(response.json())
    return validated_data.available_downloads
