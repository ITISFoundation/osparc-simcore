from typing import Annotated, TypeAlias

from pydantic import AfterValidator, AnyHttpUrl, AnyUrl, HttpUrl


def _strip_last_slash(url: str) -> str:
    return url.rstrip("/")


AnyUrlLegacy: TypeAlias = Annotated[
    str,
    AnyUrl,
    AfterValidator(_strip_last_slash),
]

AnyHttpUrlLegacy: TypeAlias = Annotated[
    str,
    AnyHttpUrl,
    AfterValidator(_strip_last_slash),
]


HttpUrlLegacy: TypeAlias = Annotated[
    str,
    HttpUrl,
    AfterValidator(_strip_last_slash),
]
