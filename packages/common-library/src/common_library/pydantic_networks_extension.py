from typing import Annotated, TypeAlias

from pydantic import AfterValidator, AnyHttpUrl, AnyUrl, HttpUrl


def _strip_last_slash(url: str) -> str:
    return url.rstrip("/")


AnyUrlLegacy: TypeAlias = Annotated[
    AnyUrl,
    AfterValidator(str),
    AfterValidator(_strip_last_slash),
]

AnyHttpUrlLegacy: TypeAlias = Annotated[
    AnyHttpUrl,
    AfterValidator(str),
    AfterValidator(_strip_last_slash),
]


HttpUrlLegacy: TypeAlias = Annotated[
    HttpUrl,
    AfterValidator(str),
    AfterValidator(_strip_last_slash),
]
