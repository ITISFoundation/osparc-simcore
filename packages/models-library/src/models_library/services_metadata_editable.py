# mypy: disable-error-code=truthy-function
from datetime import datetime
from typing import Any

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
    name: str | None = None  # type: ignore[assignment]
    thumbnail: HttpUrl | None = None
    description: str | None = None  # type: ignore[assignment]
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
    classifiers: list[str] | None = None
    quality: dict[str, Any] = {}
    model_config = ConfigDict()
