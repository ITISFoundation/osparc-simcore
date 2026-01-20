from pathlib import Path

from pydantic import NonNegativeInt

from ._models import MountId


def get_mount_id(local_mount_path: Path, index: NonNegativeInt) -> MountId:
    # unique reproducible id for the mount
    return f"{index}_{local_mount_path}".replace("/", "_")[::-1]
