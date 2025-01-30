import re
from typing import Annotated, Any, Literal

from pydantic import BaseModel, BeforeValidator, Field, HttpUrl

_MAX_LENGTH = 1_000


def _feature_descriptor_to_dict(descriptor: str) -> dict[str, Any]:
    # NOTE: this is manually added in the server side so be more robust to errors
    # Safe against polynomial runtime vulnerability due to backtracking
    if (size := len(descriptor)) and size > _MAX_LENGTH:
        msg = f"Features field too long [{size=}]"
        raise ValueError(msg)

    pattern = r"(\w{1,100}): ([^,]{1,100})"

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
