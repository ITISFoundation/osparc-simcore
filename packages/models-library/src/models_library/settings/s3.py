from pydantic import BaseSettings


class S3Config(BaseSettings):
    endpoint: str = "minio:9000"
    access_key: str = "12345678"
    secret_key: str = "12345678"
    bucket_name: str = "simcore"
    secure: bool = False

    class Config:
        case_sensitive = False
        env_prefix = "S3_"
