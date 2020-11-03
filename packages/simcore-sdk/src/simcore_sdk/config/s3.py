""" Basic configuration file for S3

"""
import logging
import warnings
from os import environ as env

import trafaret as T

warnings.warn(
    f"Module '{__name__}' will be remove in future versions. "
    "All common settings have been moved to packages/model-slibrary. "
    "Use instead 'models_library.settings.s3' ",
    DeprecationWarning,
)

log = logging.getLogger(__name__)


CONFIG_SCHEMA = T.Dict(
    {
        "endpoint": T.String(),
        "access_key": T.String(),
        "secret_key": T.String(),
        "bucket_name": T.String(),
        T.Key("secure", default=0): T.ToInt(),
    }
)


class Config:
    def __init__(self):
        S3_ENDPOINT = env.get("S3_ENDPOINT", "minio:9000")
        S3_ACCESS_KEY = env.get("S3_ACCESS_KEY", "12345678")
        S3_SECRET_KEY = env.get("S3_SECRET_KEY", "12345678")
        S3_BUCKET_NAME = env.get("S3_BUCKET_NAME", "simcore")
        S3_SECURE = env.get("S3_SECURE", "0")

        self._endpoint = S3_ENDPOINT
        self._access_key = S3_ACCESS_KEY
        self._secret_key = S3_SECRET_KEY
        self._bucket_name = S3_BUCKET_NAME
        self._secure = S3_SECURE

    @property
    def endpoint(self):
        return self._endpoint

    @property
    def access_key(self):
        return self._access_key

    @property
    def secret_key(self):
        return self._secret_key

    @property
    def bucket_name(self):
        return self._bucket_name

    @property
    def secure(self):
        return self._secure
