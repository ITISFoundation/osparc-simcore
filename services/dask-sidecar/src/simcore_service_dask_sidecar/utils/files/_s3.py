from typing import Final, TypedDict

from settings_library.s3 import S3Settings

HTTP_FILE_SYSTEM_SCHEMES: Final = ["http", "https"]
S3_FILE_SYSTEM_SCHEMES: Final = ["s3", "s3a"]

_DEFAULT_AWS_REGION: Final[str] = "us-east-1"


class ClientKWArgsDict(TypedDict, total=False):
    endpoint_url: str
    region_name: str


class S3FsSettingsDict(TypedDict):
    key: str
    secret: str
    client_kwargs: ClientKWArgsDict
    config_kwargs: dict[str, str]  # For botocore config options


def _s3fs_settings_from_s3_settings(s3_settings: S3Settings) -> S3FsSettingsDict:
    s3fs_settings: S3FsSettingsDict = {
        "key": s3_settings.S3_ACCESS_KEY.get_secret_value(),
        "secret": s3_settings.S3_SECRET_KEY.get_secret_value(),
        "client_kwargs": {},
        "config_kwargs": {
            # This setting tells the S3 client to only calculate checksums when explicitly required
            # by the operation. This avoids unnecessary checksum calculations for operations that
            # don't need them, improving performance.
            # See: https://boto3.amazonaws.com/v1/documentation/api/latest/guide/s3.html#calculating-checksums
            "request_checksum_calculation": "when_required",
            "signature_version": "s3v4",
        },
    }
    if s3_settings.S3_REGION != _DEFAULT_AWS_REGION:
        # NOTE: see https://github.com/boto/boto3/issues/125 why this is so... (sic)
        # setting it for the us-east-1 creates issue when creating buckets (which we do in tests)
        s3fs_settings["client_kwargs"]["region_name"] = s3_settings.S3_REGION
    if s3_settings.S3_ENDPOINT is not None:
        s3fs_settings["client_kwargs"]["endpoint_url"] = f"{s3_settings.S3_ENDPOINT}"
    return s3fs_settings
