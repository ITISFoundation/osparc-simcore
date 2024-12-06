import datetime as dt
from typing import Annotated

from models_library.basic_types import IDStr
from pydantic import BaseModel, ConfigDict, Field


class ApiKeyCreate(BaseModel):
    display_name: Annotated[str, Field(..., min_length=3)]
    expiration: dt.timedelta | None = None

    model_config = ConfigDict(
        from_attributes=True,
    )


class ApiKeyGet(BaseModel):
    id: IDStr
    display_name: Annotated[str, Field(..., min_length=3)]
    api_key: str | None = None
    api_secret: str | None = None

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "id": "42",
                    "display_name": "test-api-forever",
                    "api_key": "key",
                    "api_secret": "secret",
                },
            ]
        },
    )
