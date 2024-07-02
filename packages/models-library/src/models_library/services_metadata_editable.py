from datetime import datetime
from typing import Any, ClassVar

from pydantic import Field, HttpUrl

from .services_base import ServiceBase
from .services_constants import LATEST_INTEGRATION_VERSION
from .services_enums import ServiceType
from .services_types import DynamicServiceKey, ServiceKey, ServiceVersion

assert DynamicServiceKey  # nosec
assert LATEST_INTEGRATION_VERSION  # nosec
assert ServiceKey  # nosec
assert ServiceType  # nosec
assert ServiceVersion  # nosec


class ServiceMetaDataEditable(ServiceBase):
    # Overrides all fields of ServiceBase for a partial update all members must be Optional

    name: str | None
    thumbnail: HttpUrl | None
    description: str | None
    deprecated: datetime | None = Field(
        default=None,
        description="If filled with a date, then the service is to be deprecated at that date (e.g. cannot start anymore)",
    )

    # user-defined metatada
    classifiers: list[str] | None
    quality: dict[str, Any] = {}

    class Config:
        schema_extra: ClassVar[dict[str, Any]] = {
            "example": {
                "key": "simcore/services/dynamic/sim4life",
                "version": "1.0.9",
                "name": "sim4life",
                "description": "s4l web",
                "thumbnail": "https://thumbnailit.org/image",
                "quality": {
                    "enabled": True,
                    "tsr_target": {
                        f"r{n:02d}": {"level": 4, "references": ""}
                        for n in range(1, 11)
                    },
                    "annotations": {
                        "vandv": "",
                        "limitations": "",
                        "certificationLink": "",
                        "certificationStatus": "Uncertified",
                    },
                    "tsr_current": {
                        f"r{n:02d}": {"level": 0, "references": ""}
                        for n in range(1, 11)
                    },
                },
            }
        }
