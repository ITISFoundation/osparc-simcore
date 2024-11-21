from typing import Any

from pydantic import AnyUrl, BaseModel, Field


class AppStatusCheck(BaseModel):
    app_name: str = Field(..., description="Application name")
    version: str = Field(..., description="Application's version")
    services: dict[str, Any] = Field(
        default_factory=dict,
        description="Other backend services connected from this service",
        json_schema_extra={"default": {}},
    )

    sessions: dict[str, Any] | None = Field(
        default_factory=dict,
        description="Client sessions info. If single session per app, then is denoted as main",
        json_schema_extra={"default": {}},
    )

    url: AnyUrl | None = Field(
        default=None,
        description="Link to current resource",
    )
    diagnostics_url: AnyUrl | None = Field(
        default=None,
        description="Link to diagnostics report sub-resource. This MIGHT take some time to compute",
    )
