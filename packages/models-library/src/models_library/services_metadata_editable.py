# mypy: disable-error-code=truthy-function
from datetime import datetime
from typing import Annotated, Any

from pydantic import ConfigDict, Field, HttpUrl

from .services_base import ServiceBaseDisplay
from .services_constants import LATEST_INTEGRATION_VERSION
from .services_enums import ServiceType
from .services_types import DynamicServiceKey, ServiceKey, ServiceVersion

assert DynamicServiceKey  # nosec
assert LATEST_INTEGRATION_VERSION  # nosec
assert ServiceKey  # nosec
assert ServiceType  # nosec
assert ServiceVersion  # nosec


class ServiceMetaDataEditable(ServiceBaseDisplay):
    # Overrides ServiceBaseDisplay fields to Optional for a partial update
    name: str | None  # type: ignore[assignment]
    thumbnail: Annotated[str, HttpUrl] | None
    description: str | None  # type: ignore[assignment]
    description_ui: bool = False
    version_display: str | None = None

    # Below fields only in the database ----
    deprecated: datetime | None = Field(
        default=None,
        description="Owner can set the date to retire the service. Three possibilities:"
        "If None, the service is marked as `published`;"
        "If now<deprecated the service is marked as deprecated;"
        "If now>=deprecated, the service is retired",
    )
    classifiers: list[str] | None
    quality: dict[str, Any] = Field(
        default_factory=dict, json_schema_extra={"default": {}}
    )

    model_config = ConfigDict(
        json_schema_extra={
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
                "classifiers": [],
            }
        }
    )
