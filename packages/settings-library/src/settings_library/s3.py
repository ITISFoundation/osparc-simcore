from .base import BaseCustomSettings


class S3Settings(BaseCustomSettings):
    # TODO: try to remove defaults if this works also remove _RequiredS3Settings
    S3_ENDPOINT: str = "minio:9000"
    S3_ACCESS_KEY: str = "12345678"
    S3_SECRET_KEY: str = "12345678"
    S3_BUCKET_NAME: str = "simcore"
    S3_SECURE: bool = False
