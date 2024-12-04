from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class ApiKeyGet(BaseModel):
    display_name: Annotated[str, Field(..., min_length=3)]
    api_key: str
    api_secret: str

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "display_name": "test-api-forever",
                    "api_key": "key",
                    "api_secret": "secret",
                },
            ]
        },
    )
