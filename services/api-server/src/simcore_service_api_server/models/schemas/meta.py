from models_library.api_schemas__common.meta import BaseMeta
from pydantic import AnyHttpUrl, ConfigDict


class Meta(BaseMeta):
    docs_url: AnyHttpUrl
    docs_dev_url: AnyHttpUrl
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "simcore_service_foo",
                "version": "2.4.45",
                "released": {"v1": "1.3.4", "v2": "2.4.45"},
                "docs_url": "https://api.osparc.io/dev/doc",
                "docs_dev_url": "https://api.osparc.io/dev/doc",
            }
        }
    )
