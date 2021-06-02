# pylint: disable=global-statement
from enum import Enum


class BootMode(Enum):
    CPU = "CPU"
    GPU = "GPU"
    MPI = "MPI"
