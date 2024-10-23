from models_library.api_schemas__common.meta import BaseMeta
from pydantic import ConfigDict, HttpUrl


class Meta(BaseMeta):
    docs_url: HttpUrl
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "simcore_service_payments",
                "version": "2.4.45",
                "docs_url": "https://foo.io/doc",
            }
        }
    )
