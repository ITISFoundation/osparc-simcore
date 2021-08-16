import warnings

from pydantic import BaseSettings

warnings.warn(
    "models_library.settings will be mostly replaced by settings_library in future versions. "
    "SEE https://github.com/ITISFoundation/osparc-simcore/pull/2395 for details",
    DeprecationWarning,
)


class S3Config(BaseSettings):
    endpoint: str = "minio:9000"
    access_key: str = "12345678"
    secret_key: str = "12345678"
    bucket_name: str = "simcore"
    secure: bool = False

    class Config:
        case_sensitive = False
        env_prefix = "S3_"
