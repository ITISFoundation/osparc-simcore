from typing import Annotated, TypeAlias

from pydantic import AfterValidator, AnyHttpUrl


def _strip_last_slash(url: str) -> str:
    return url.rstrip("/")


AnyHttpUrlLegacy: TypeAlias = Annotated[
    str, AnyHttpUrl, AfterValidator(_strip_last_slash)
]
