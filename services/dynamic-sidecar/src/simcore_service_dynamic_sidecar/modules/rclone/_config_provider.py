from enum import Enum, auto
from typing import Final

from settings_library.utils_r_clone import get_s3_r_clone_config
from simcore_service_dynamic_sidecar.core.settings import ApplicationSettings

CONFIG_KEY: Final[str] = "MOUNT_REMOTE"


class MountRemoteType(Enum):
    S3 = auto()


def get_config_content(
    settings: ApplicationSettings, mount_remote_type: MountRemoteType
) -> str:
    match mount_remote_type:
        case MountRemoteType.S3:
            return get_s3_r_clone_config(
                settings.DY_SIDECAR_R_CLONE_SETTINGS, s3_config_key=CONFIG_KEY
            )
        case _:
            msg = f"Mount type {mount_remote_type} not implemented"
            raise NotImplementedError(msg)
