from typing import Any, Optional

from pydantic import AnyUrl, BaseModel, Field


class AppStatusCheck(BaseModel):
    app_name: str = Field(..., description="Application name")
    version: str = Field(..., description="Application's version")
    services: dict[str, Any] = Field(
        default={}, description="Other backend services connected from this service"
    )

    sessions: Optional[dict[str, Any]] = Field(
        default={},
        description="Client sessions info. If single session per app, then is denoted as main",
    )

    url: Optional[AnyUrl] = Field(
        default=None,
        description="Link to current resource",
    )
    diagnostics_url: Optional[AnyUrl] = Field(
        default=None,
        description="Link to diagnostics report sub-resource. This MIGHT take some time to compute",
    )
