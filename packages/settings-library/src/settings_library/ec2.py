from pydantic import Field

from .base import BaseCustomSettings


class EC2Settings(BaseCustomSettings):
    EC2_ACCESS_KEY_ID: str
    EC2_ENDPOINT: str | None = Field(
        default=None, description="do not define if using standard AWS"
    )
    EC2_REGION_NAME: str = "us-east-1"
    EC2_SECRET_ACCESS_KEY: str
