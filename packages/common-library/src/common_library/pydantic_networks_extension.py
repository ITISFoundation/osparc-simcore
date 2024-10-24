from typing import Annotated, TypeAlias

from pydantic import AfterValidator, AnyHttpUrl, HttpUrl
from pydantic_core import Url


def _strip_last_slash(url: Url) -> str:
    return f"{url}".rstrip("/")


AnyHttpUrlLegacy: TypeAlias = Annotated[
    AnyHttpUrl,
    AfterValidator(_strip_last_slash),
]


HttpUrlLegacy: TypeAlias = Annotated[
    HttpUrl,
    AfterValidator(_strip_last_slash),
]
