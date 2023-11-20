from typing import Any, ClassVar

from models_library.api_schemas__common.meta import BaseMeta
from pydantic import HttpUrl


class Meta(BaseMeta):
    docs_url: HttpUrl

    class Config:
        schema_extra: ClassVar[dict[str, Any]] = {
            "example": {
                "name": "simcore_service_dynamic_scheduler",
                "version": "2.4.45",
                "docs_url": "https://foo.io/doc",
            }
        }
