from typing import Annotated, TypeAlias

from pydantic import AfterValidator, AnyHttpUrl, AnyUrl


def _strip_last_slash(url: str) -> str:
    return url.rstrip("/")


AnyHttpUrlLegacy: TypeAlias = Annotated[
    str, AnyHttpUrl, AfterValidator(_strip_last_slash)
]

AnyUrlLegacy: TypeAlias = Annotated[str, AnyUrl, AfterValidator(_strip_last_slash)]
