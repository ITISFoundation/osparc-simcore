from typing import Annotated

from models_library.api_schemas__common.meta import BaseMeta
from models_library.basic_types import VersionStr
from pydantic import AnyHttpUrl, ConfigDict, Field, StringConstraints


class Meta(BaseMeta):
    docs_url: Annotated[AnyHttpUrl, StringConstraints(max_length=65536)]
    docs_dev_url: Annotated[AnyHttpUrl, StringConstraints(max_length=65536)]
    released: dict[str, VersionStr] = Field(
        default=None, description="Maps every route's path tag with a released version"
    )
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
