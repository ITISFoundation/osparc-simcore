from pydantic import BaseModel, ConfigDict, Field

from ..basic_types import VersionStr


class BaseMeta(BaseModel):
    name: str
    version: VersionStr
    released: dict[str, VersionStr] | None = Field(
        default=None, description="Maps every route's path tag with a released version"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "simcore_service_foo",
                "version": "2.4.45",
                "released": {"v1": "1.3.4", "v2": "2.4.45"},
            }
        }
    )
