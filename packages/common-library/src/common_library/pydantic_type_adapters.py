from typing import Final

from common_library.pydantic_networks_extension import AnyHttpUrlLegacy, AnyUrlLegacy
from pydantic import TypeAdapter

AnyUrlLegacyAdapter: Final[TypeAdapter[AnyUrlLegacy]] = TypeAdapter(AnyUrlLegacy)

AnyHttpUrlLegacyAdapter: Final[TypeAdapter] = TypeAdapter(AnyHttpUrlLegacy)
