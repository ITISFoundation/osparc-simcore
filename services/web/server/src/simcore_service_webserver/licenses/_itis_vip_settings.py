from typing import Annotated

from common_library.pydantic_basic_types import ShortTruncatedStr
from models_library.basic_types import IDStr
from pydantic import AfterValidator, HttpUrl
from settings_library.base import BaseCustomSettings


def _validate_url_contains_category(url: str) -> str:
    if "{category}" not in url:
        msg = "URL must contain '{category}'"
        raise ValueError(msg)
    return url


class ItisVipSettings(BaseCustomSettings):
    ITIS_VIP_API_URL: Annotated[str, AfterValidator(_validate_url_contains_category)]
    ITIS_VIP_CATEGORIES: list[str]

    def get_urls(self) -> list[HttpUrl]:
        return [
            HttpUrl(self.ITIS_VIP_API_URL.format(category=category))
            for category in self.ITIS_VIP_CATEGORIES
        ]


class ItisVipCategorySettings(BaseCustomSettings):
    ITIS_VIP_CATEGORY_URL: HttpUrl
    ITIS_VIP_CATEGORY_ID: IDStr  # use same as in vip-api
    ITIS_VIP_CATEGORY_DISPLAY_NAME: ShortTruncatedStr
