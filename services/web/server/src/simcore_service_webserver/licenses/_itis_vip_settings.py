from typing import Annotated

from pydantic import AfterValidator, HttpUrl
from settings_library.base import BaseCustomSettings

from ._itis_vip_models import CategoryDisplay, CategoryID, CategoryTuple


def _validate_url_contains_category(url: str) -> str:
    if "{category}" not in url:
        msg = "URL must contain '{category}'"
        raise ValueError(msg)
    return url


class ItisVipSettings(BaseCustomSettings):
    LICENSES_ITIS_VIP_API_URL: Annotated[
        str, AfterValidator(_validate_url_contains_category)
    ]
    LICENSES_ITIS_VIP_CATEGORIES: dict[CategoryID, CategoryDisplay]

    def get_urls(self) -> list[HttpUrl]:
        return [
            HttpUrl(self.LICENSES_ITIS_VIP_API_URL.format(category=category))
            for category in self.LICENSES_ITIS_VIP_CATEGORIES
        ]

    def to_categories(self) -> list[CategoryTuple]:
        return [
            CategoryTuple(
                url=HttpUrl(
                    self.LICENSES_ITIS_VIP_API_URL.format(category=category_id)
                ),
                id=category_id,
                display=category_display,
            )
            for category_id, category_display in self.LICENSES_ITIS_VIP_CATEGORIES.items()
        ]
