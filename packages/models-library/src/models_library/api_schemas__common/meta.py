from pydantic import BaseModel, ConfigDict, Field

from ..basic_types import VersionStr


class BaseMeta(BaseModel):
    name: str
    version: VersionStr
    released: dict[str, VersionStr] | None = Field(
        default=None, description="Maps every route's path tag with a released version"
    )
    model_config = ConfigDict()
