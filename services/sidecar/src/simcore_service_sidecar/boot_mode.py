# pylint: disable=global-statement

from enum import Enum


class BootMode(Enum):
    CPU = "CPU"
    GPU = "GPU"
    MPI = "MPI"


_sidecar_boot_mode: BootMode = None


def get_boot_mode() -> BootMode:
    global _sidecar_boot_mode
    return _sidecar_boot_mode


def set_boot_mode(boot_mode: BootMode) -> None:
    global _sidecar_boot_mode
    _sidecar_boot_mode = boot_mode
