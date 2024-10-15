from typing import Final

from common_library.pydantic_networks_extension import AnyHttpUrlLegacy, AnyUrlLegacy
from pydantic import ByteSize, TypeAdapter

AnyUrlLegacyAdapter: Final[TypeAdapter[AnyUrlLegacy]] = TypeAdapter(AnyUrlLegacy)

AnyHttpUrlLegacyAdapter: Final[TypeAdapter[AnyHttpUrlLegacy]] = TypeAdapter(
    AnyHttpUrlLegacy
)

ByteSizeAdapter = TypeAdapter(ByteSize)
