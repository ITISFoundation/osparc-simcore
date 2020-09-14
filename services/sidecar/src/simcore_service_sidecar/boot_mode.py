# pylint: disable=global-statement

from enum import Enum
from typing import Optional


class BootMode(Enum):
    CPU = "CPU"
    GPU = "GPU"
    MPI = "MPI"


_sidecar_boot_mode: Optional[BootMode] = None


def get_boot_mode() -> Optional[BootMode]:
    global _sidecar_boot_mode
    return _sidecar_boot_mode


def set_boot_mode(boot_mode: BootMode) -> None:
    global _sidecar_boot_mode
    _sidecar_boot_mode = boot_mode
