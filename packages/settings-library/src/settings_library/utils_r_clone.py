import configparser
from copy import deepcopy
from io import StringIO
from typing import Dict

from .r_clone import RCloneSettings, S3Provider

_COMMON_ENTRIES: Dict[str, str] = {
    "type": "s3",
    "access_key_id": "{access_key}",
    "secret_access_key": "{secret_key}",
    "region": "us-east-1",
    "acl": "private",
}

_PROVIDER_ENDTIRES: Dict[S3Provider, Dict[str, str]] = {
    S3Provider.AWS: {"provider": "AWS"},
    S3Provider.CEPH: {"provider": "Ceph", "endpoint": "{endpoint}"},
    S3Provider.MINIO: {"provider": "Minio", "endpoint": "{endpoint}"},
}


def _format_config(entries: Dict[str, str]) -> str:
    config = configparser.ConfigParser()
    config["dst"] = entries
    with StringIO() as string_io:
        config.write(string_io)
        string_io.seek(0)
        return string_io.read()


def get_r_clone_config(r_clone_settings: RCloneSettings) -> str:
    provider = r_clone_settings.R_CLONE_PROVIDER
    entries = deepcopy(_COMMON_ENTRIES)
    entries.update(_PROVIDER_ENDTIRES[provider])

    r_clone_config_template = _format_config(entries=entries)

    # replace entries in template
    r_clone_config = r_clone_config_template.format(
        endpoint=r_clone_settings.R_CLONE_S3.S3_ENDPOINT,
        access_key=r_clone_settings.R_CLONE_S3.S3_ACCESS_KEY,
        secret_key=r_clone_settings.R_CLONE_S3.S3_SECRET_KEY,
    )
    return r_clone_config
