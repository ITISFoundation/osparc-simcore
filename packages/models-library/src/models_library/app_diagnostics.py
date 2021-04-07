from typing import Any, Dict, Optional

from pydantic import AnyUrl, BaseModel, Field


class AppStatusCheck(BaseModel):
    app_name: str = Field(..., description="Application name")
    version: str = Field(..., description="Application's version")
    services: Dict[str, Any] = Field(
        {}, description="Other backend services connected from this service"
    )

    url: Optional[AnyUrl] = Field(
        None,
        description="Link to current resource",
    )
    diagnostics_url: Optional[AnyUrl] = Field(
        None,
        description="Link to diagnostics report sub-resource. This MIGHT take some time to compute",
    )
