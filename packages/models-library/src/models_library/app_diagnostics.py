from typing import Annotated, Any

from pydantic import AnyUrl, BaseModel, Field

from ._compat import Undefined

_Unset: Any = Undefined


class AppStatusCheck(BaseModel):
    app_name: str = Field(..., description="Application name")
    version: str = Field(..., description="Application's version")
    services: Annotated[
        dict[str, Any],
        Field(
            default_factory=dict,
            description="Other backend services connected from this service",
            json_schema_extra={"default": {}},
        ),
    ] = _Unset

    sessions: Annotated[
        dict[str, Any] | None,
        Field(
            default_factory=dict,
            description="Client sessions info. If single session per app, then is denoted as main",
            json_schema_extra={"default": {}},
        ),
    ] = _Unset

    url: AnyUrl | None = Field(
        default=None,
        description="Link to current resource",
    )

    diagnostics_url: Annotated[
        AnyUrl | None,
        Field(
            description="Link to diagnostics report sub-resource. This MIGHT take some time to compute",
        ),
    ] = None
