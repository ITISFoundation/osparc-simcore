from typing import Annotated

from pydantic import AnyHttpUrl, BaseModel, Field

from ..basic_types import IDStr


class S3SettingsGet(BaseModel):
    S3_ACCESS_KEY: str
    S3_BUCKET_NAME: IDStr
    S3_ENDPOINT: Annotated[AnyHttpUrl | None, Field(description="do not define if using standard AWS")] = None
    S3_REGION: IDStr
    S3_SECRET_KEY: str
