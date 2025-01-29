from typing import Annotated

from pydantic import AfterValidator, Field, HttpUrl
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


class LicensesSettings(BaseCustomSettings):
    LICENSES_ITIS_VIP: Annotated[
        ItisVipSettings | None, Field(description="Settings for VIP license models")
    ]
    # other licenses resources come here
