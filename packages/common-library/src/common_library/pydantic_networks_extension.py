from typing import Annotated, TypeAlias
from pydantic import AfterValidator, AnyHttpUrl


AnyHttpUrlLegacy: TypeAlias = Annotated[str, AnyHttpUrl, AfterValidator(lambda u: u.rstrip("/"))]
