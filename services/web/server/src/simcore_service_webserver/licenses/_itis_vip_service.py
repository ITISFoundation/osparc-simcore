import re
from typing import Annotated, Any, Literal
from urllib.parse import urlparse

import httpx
import pytest
from pydantic import BaseModel, BeforeValidator, Field, HttpUrl, ValidationError
from servicelib.aiohttp import status
from settings_library.base import BaseCustomSettings


class ItisVipSettings(BaseCustomSettings):
    ITIS_VIP_API_URL: str
    ITIS_VIP_CATEGORIES: list[str]

    def get_urls(self) -> list[HttpUrl]:
        return [
            HttpUrl(self.ITIS_VIP_API_URL.format(category=category))
            for category in self.ITIS_VIP_CATEGORIES
        ]


def _feature_descriptor_to_dict(descriptor: str) -> dict[str, Any]:
    # NOTE: this is manually added in the server side so be more robust to errors
    pattern = r"(\w+): ([^,]+)"
    matches = re.findall(pattern, descriptor.strip("{}"))
    return dict(matches)


class AvailableDownload(BaseModel):
    id: Annotated[int, Field(alias="ID")]
    description: Annotated[str, Field(alias="Description")]
    thumbnail: Annotated[str, Field(alias="Thumbnail")]
    features: Annotated[
        dict[str, Any],
        BeforeValidator(_feature_descriptor_to_dict),
        Field(alias="Features"),
    ]
    doi: Annotated[str, Field(alias="DOI")]
    license_key: Annotated[str | None, Field(alias="LicenseKey")]
    license_version: Annotated[str | None, Field(alias="LicenseVersion")]
    protection: Annotated[Literal["Code", "PayPal"], Field(alias="Protection")]
    available_from_url: Annotated[HttpUrl | None, Field(alias="AvailableFromURL")]


class ResponseData(BaseModel):
    msg: int | None = None  # still not used
    available_downloads: Annotated[
        list[AvailableDownload], Field(alias="availableDownloads")
    ]


async def get_downloadable_items(
    client: httpx.AsyncClient, url: HttpUrl
) -> list[AvailableDownload]:
    response = await client.post(f"{url}")
    assert response.status_code == status.HTTP_200_OK
    validated_data = ResponseData.model_validate(**response.json())
    return validated_data.available_downloads


async def fetch_vip_downloadables(settings: ItisVipSettings):
    urls, categories = settings.get_urls(), settings.ITIS_VIP_CATEGORIES

    base_url = f"{urls[0].scheme}://{urlparse(f'{urls[0]}').netloc}"

    async with httpx.AsyncClient() as client:
        for url in urls:
            response = await client.post(url)
            assert response.status_code == status.HTTP_200_OK
            response_json = response.json()

            try:
                validated_data = ResponseData(**response_json)
            except ValidationError as e:
                pytest.fail(f"Response validation failed: {e}")
