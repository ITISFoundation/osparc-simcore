from typing import Annotated, TypeAlias

from pydantic import AfterValidator, AnyHttpUrl, AnyUrl, FileUrl, HttpUrl
from pydantic_core import Url


def _strip_last_slash(url: Url) -> str:
    return f"{url}".rstrip("/")


AnyUrlLegacy: TypeAlias = Annotated[
    AnyUrl,
    AfterValidator(_strip_last_slash),
]

AnyHttpUrlLegacy: TypeAlias = Annotated[
    AnyHttpUrl,
    AfterValidator(_strip_last_slash),
]


HttpUrlLegacy: TypeAlias = Annotated[
    HttpUrl,
    AfterValidator(_strip_last_slash),
]

FileUrlLegacy: TypeAlias = Annotated[
    FileUrl,
    AfterValidator(_strip_last_slash),
]
