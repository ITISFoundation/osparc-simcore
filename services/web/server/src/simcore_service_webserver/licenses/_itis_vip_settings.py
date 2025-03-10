from typing import Annotated

from pydantic import AfterValidator, HttpUrl
from settings_library.base import BaseCustomSettings

from ._itis_vip_models import CategoryDisplay, CategoryID, CategoryTuple


def _validate_url_contains_category(url: str) -> str:
    if "{category}" not in url:
        msg = "URL must contain '{category}'"
        raise ValueError(msg)
    return url


def _to_categories(
    api_url: str, category_map: dict[CategoryID, CategoryDisplay]
) -> list[CategoryTuple]:
    return [
        CategoryTuple(
            url=HttpUrl(api_url.format(category=category_id)),
            id=category_id,
            display=category_display,
        )
        for category_id, category_display in category_map.items()
    ]


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
        return _to_categories(
            self.LICENSES_ITIS_VIP_API_URL,
            self.LICENSES_ITIS_VIP_CATEGORIES,
        )


class SpeagPhantomsSettings(BaseCustomSettings):
    LICENSES_SPEAG_PHANTOMS_API_URL: Annotated[
        str, AfterValidator(_validate_url_contains_category)
    ]
    LICENSES_SPEAG_PHANTOMS_CATEGORIES: dict[CategoryID, CategoryDisplay]

    def to_categories(self) -> list[CategoryTuple]:
        return _to_categories(
            self.LICENSES_SPEAG_PHANTOMS_API_URL,
            self.LICENSES_SPEAG_PHANTOMS_CATEGORIES,
        )
