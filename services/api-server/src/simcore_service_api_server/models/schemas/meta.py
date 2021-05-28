from typing import Dict, Optional

from pydantic import AnyHttpUrl, BaseModel, Field

from ..basic_types import VersionStr


class Meta(BaseModel):
    name: str
    version: VersionStr
    released: Optional[Dict[str, VersionStr]] = Field(
        None, description="Maps every route's path tag with a released version"
    )
    docs_url: AnyHttpUrl = "https://docs.osparc.io"
    docs_dev_url: AnyHttpUrl = "https://api.osparc.io/dev/docs"

    class Config:
        schema_extra = {
            "example": {
                "name": "simcore_service_foo",
                "version": "2.4.45",
                "released": {"v1": "1.3.4", "v2": "2.4.45"},
                "doc_url": "https://api.osparc.io/doc",
                "doc_dev_url": "https://api.osparc.io/dev/doc",
            }
        }
