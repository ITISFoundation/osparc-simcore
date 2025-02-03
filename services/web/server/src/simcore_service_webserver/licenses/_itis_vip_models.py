import re
from typing import Annotated, Any, Literal, NamedTuple, NotRequired, Self, TypeAlias

from models_library.basic_types import IDStr
from pydantic import (
    BaseModel,
    BeforeValidator,
    Field,
    HttpUrl,
    StringConstraints,
    TypeAdapter,
)
from typing_extensions import TypedDict

_max_str_adapter = TypeAdapter(
    Annotated[str, StringConstraints(strip_whitespace=True, max_length=1_000)]
)


def _feature_descriptor_to_dict(descriptor: str) -> dict[str, Any]:
    # NOTE: this is manually added in the server side so be more robust to errors
    descriptor = _max_str_adapter.validate_python(descriptor.strip("{}"))
    pattern = r"(\w{1,100}): ([^,]{1,100})"
    matches = re.findall(pattern, descriptor)
    return dict(matches)


#
# ITIS-VIP API Schema
#


class FeaturesDict(TypedDict):
    name: str
    version: str
    sex: NotRequired[str]
    age: NotRequired[str]
    weight: NotRequired[str]
    height: NotRequired[str]
    date: NotRequired[str]
    ethnicity: NotRequired[str]
    functionality: NotRequired[str]


class ItisVipData(BaseModel):
    id: Annotated[int, Field(alias="ID")]
    description: Annotated[str, Field(alias="Description")]
    thumbnail: Annotated[str, Field(alias="Thumbnail")]
    features: Annotated[
        dict[str, Any],  # NOTE: for the moment FeaturesDict is NOT used
        BeforeValidator(_feature_descriptor_to_dict),
        Field(alias="Features"),
    ]
    doi: Annotated[str | None, Field(alias="DOI")]
    license_key: Annotated[str | None, Field(alias="LicenseKey")]
    license_version: Annotated[str | None, Field(alias="LicenseVersion")]
    protection: Annotated[Literal["Code", "PayPal"], Field(alias="Protection")]
    available_from_url: Annotated[HttpUrl | None, Field(alias="AvailableFromURL")]


class ItisVipApiResponse(BaseModel):
    msg: int | None = None  # still not used
    available_downloads: Annotated[list[ItisVipData], Field(alias="availableDownloads")]


#
# RESOURCE
#


class ItisVipResourceData(BaseModel):
    category_id: IDStr
    category_display: str
    source: Annotated[
        dict[str, Any], Field(description="Original published data in the api")
    ]

    @classmethod
    def create(
        cls, category_id: IDStr, category_display: str, source: ItisVipData
    ) -> Self:
        return cls(
            category_id=category_id,
            category_display=category_display,
            # NOTE: ensures source data is the same as the one in the original VIP API model
            source=source.model_dump(mode="json", by_alias=True),
        )


#
# INTERNAL
#

CategoryID: TypeAlias = IDStr
CategoryDisplay: TypeAlias = str


class CategoryTuple(NamedTuple):
    url: HttpUrl
    id: CategoryID
    display: CategoryDisplay
