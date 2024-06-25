from pydantic import ByteSize, NonNegativeInt, validator
from pydantic.tools import parse_raw_as
from settings_library.base import BaseCustomSettings

from ._constants import GB

_DEFAULT_MAX_NANO_CPUS_VALUE = 1 * pow(10, 9)
_DEFAULT_MAX_MEMORY_VALUE = 2 * GB


class ComputationalServices(BaseCustomSettings):
    DEFAULT_MAX_NANO_CPUS: NonNegativeInt = _DEFAULT_MAX_NANO_CPUS_VALUE
    DEFAULT_MAX_MEMORY: ByteSize = parse_raw_as(
        ByteSize, f"{_DEFAULT_MAX_MEMORY_VALUE}"
    )
    DEFAULT_RUNTIME_TIMEOUT: NonNegativeInt = 0

    @validator("DEFAULT_MAX_NANO_CPUS", pre=True)
    @classmethod
    def _set_default_cpus_if_negative(cls, v):
        if v is None or v == "" or int(v) <= 0:
            v = _DEFAULT_MAX_NANO_CPUS_VALUE
        return v

    @validator("DEFAULT_MAX_MEMORY", pre=True)
    @classmethod
    def _set_default_memory_if_negative(cls, v):
        if v is None or v == "" or int(v) <= 0:
            v = _DEFAULT_MAX_MEMORY_VALUE
        return v
