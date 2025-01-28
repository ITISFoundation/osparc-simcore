from typing import Annotated

from pydantic import AnyHttpUrl, BeforeValidator, Field, TypeAdapter
from pydantic_settings import SettingsConfigDict

from .base import BaseCustomSettings

ANY_HTTP_URL_ADAPTER: TypeAdapter = TypeAdapter(AnyHttpUrl)


def _validate_url(value: str | None) -> str | None:
    if value is not None:
        return str(ANY_HTTP_URL_ADAPTER.validate_python(value))
    return value


class EC2Settings(BaseCustomSettings):
    EC2_ACCESS_KEY_ID: str
    EC2_ENDPOINT: Annotated[
        str | None,
        BeforeValidator(_validate_url),
        Field(description="do not define if using standard AWS"),
    ] = None
    EC2_REGION_NAME: str = "us-east-1"
    EC2_SECRET_ACCESS_KEY: str

    model_config = SettingsConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "EC2_ACCESS_KEY_ID": "my_access_key_id",
                    "EC2_ENDPOINT": "https://my_ec2_endpoint.com",
                    "EC2_REGION_NAME": "us-east-1",
                    "EC2_SECRET_ACCESS_KEY": "my_secret_access_key",
                }
            ],
        }
    )
