from typing import Any, ClassVar

from models_library.basic_types import VersionStr
from pydantic import BaseModel, HttpUrl


class Meta(BaseModel):
    name: str
    version: VersionStr
    docs_url: HttpUrl

    class Config:
        schema_extra: ClassVar[dict[str, Any]] = {
            "example": {
                "name": "simcore_service_payments",
                "version": "2.4.45",
                "docs_url": "https://foo.io/doc",
            }
        }
