from typing import Annotated, TypeAlias

from models_library.basic_types import IDStr
from pydantic import AfterValidator, HttpUrl
from settings_library.base import BaseCustomSettings


def _validate_url_contains_category(url: str) -> str:
    if "{category}" not in url:
        msg = "URL must contain '{category}'"
        raise ValueError(msg)
    return url


CategoryID: TypeAlias = IDStr
CategoryDisplay: TypeAlias = str


class ItisVipSettings(BaseCustomSettings):
    ITIS_VIP_API_URL: Annotated[str, AfterValidator(_validate_url_contains_category)]
    ITIS_VIP_CATEGORIES: dict[CategoryID, CategoryDisplay]

    def get_urls(self) -> list[HttpUrl]:
        return [
            HttpUrl(self.ITIS_VIP_API_URL.format(category=category))
            for category in self.ITIS_VIP_CATEGORIES
        ]
