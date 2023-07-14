import configparser
from copy import deepcopy
from io import StringIO

from .r_clone import RCloneSettings, S3Provider

_COMMON_SETTINGS_OPTIONS: dict[str, str] = {
    "type": "s3",
    "access_key_id": "{access_key}",
    "secret_access_key": "{secret_key}",
    "region": "{aws_region}",
    "acl": "private",
}

_PROVIDER_SETTINGS_OPTIONS: dict[S3Provider, dict[str, str]] = {
    # NOTE: # AWS_SESSION_TOKEN should be required for STS
    S3Provider.AWS: {"provider": "AWS"},
    S3Provider.CEPH: {"provider": "Ceph", "endpoint": "{endpoint}"},
    S3Provider.MINIO: {"provider": "Minio", "endpoint": "{endpoint}"},
}


def _format_config(settings_options: dict[str, str], s3_config_key: str) -> str:
    config = configparser.ConfigParser()
    config[s3_config_key] = settings_options
    with StringIO() as string_io:
        config.write(string_io)
        string_io.seek(0)
        return string_io.read()


def get_r_clone_config(r_clone_settings: RCloneSettings, *, s3_config_key: str) -> str:
    """
    Arguments:
        r_clone_settings -- current rclone configuration
        s3_config_key -- used by the cli to reference the rclone configuration
            it is used to make the cli command more readable

    Returns:
        stringified *.ini rclone configuration
    """
    settings_options: dict[str, str] = deepcopy(_COMMON_SETTINGS_OPTIONS)
    settings_options.update(
        _PROVIDER_SETTINGS_OPTIONS[r_clone_settings.R_CLONE_PROVIDER]
    )

    r_clone_config_template = _format_config(
        settings_options=settings_options, s3_config_key=s3_config_key
    )

    # replace entries in template
    return r_clone_config_template.format(
        endpoint=r_clone_settings.R_CLONE_S3.S3_ENDPOINT,
        access_key=r_clone_settings.R_CLONE_S3.S3_ACCESS_KEY,
        secret_key=r_clone_settings.R_CLONE_S3.S3_SECRET_KEY,
        aws_region=r_clone_settings.R_CLONE_S3.S3_REGION,
    )


def resolve_provider(s3_provider: S3Provider) -> str:
    return _PROVIDER_SETTINGS_OPTIONS[s3_provider]["provider"]
