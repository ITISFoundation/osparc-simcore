from enum import Enum, auto
from typing import Final

from settings_library.r_clone import RCloneSettings
from settings_library.utils_r_clone import get_s3_r_clone_config

CONFIG_KEY: Final[str] = "MOUNT_REMOTE"


class MountRemoteType(Enum):
    S3 = auto()
    # NOTE: oauth authorization pattern needs to be setup for non S3 providers


def get_config_content(r_clone_settings: RCloneSettings, mount_remote_type: MountRemoteType) -> str:
    match mount_remote_type:
        case MountRemoteType.S3:
            return get_s3_r_clone_config(r_clone_settings, s3_config_key=CONFIG_KEY)
        case _:
            msg = f"Mount type {mount_remote_type} not implemented"
            raise NotImplementedError(msg)
