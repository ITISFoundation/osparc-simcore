import re
from typing import Annotated, Any, Literal, NamedTuple, TypeAlias

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


class FeaturesDict(TypedDict, total=False):
    # All optional (for now)
    name: str
    version: str
    sex: str
    age: str
    weight: str
    height: str
    date: str
    ethnicity: str
    functionality: str


class ItisVipData(BaseModel):
    # Designed to parse items from response from VIP-API
    id: Annotated[int, Field(alias="ID")]
    description: Annotated[str, Field(alias="Description")]
    thumbnail: Annotated[str, Field(alias="Thumbnail")]
    features: Annotated[
        FeaturesDict,
        BeforeValidator(_feature_descriptor_to_dict),
        Field(alias="Features"),
    ]
    doi: Annotated[str | None, Field(alias="DOI")]
    license_key: Annotated[
        str,
        Field(
            alias="LicenseKey",
            description="NOTE: skips VIP w/o license key",
        ),
    ]
    license_version: Annotated[
        str,
        Field(
            alias="LicenseVersion",
            description="NOTE: skips VIP w/o license version",
        ),
    ]
    protection: Annotated[Literal["Code", "PayPal"], Field(alias="Protection")]
    available_from_url: Annotated[HttpUrl | None, Field(alias="AvailableFromURL")]


class ItisVipResourceData(BaseModel):
    category_id: IDStr
    category_display: str
    source: Annotated[
        ItisVipData, Field(description="Original published data in the api")
    ]
    terms_of_use_url: HttpUrl | None = None


CategoryID: TypeAlias = IDStr
CategoryDisplay: TypeAlias = str


class CategoryTuple(NamedTuple):
    url: HttpUrl
    id: CategoryID
    display: CategoryDisplay
