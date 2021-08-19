from pydantic import ByteSize, NonNegativeInt, validator
from settings_library.base import BaseCustomSettings

_DEFAULT_MAX_NANO_CPUS_VALUE = 4 * pow(10, 9)
_DEFAULT_MAX_MEMORY_VALUE = 2 * pow(1024, 3)  # 2 GiB


class CompServices(BaseCustomSettings):
    DEFAULT_MAX_NANO_CPUS: NonNegativeInt = _DEFAULT_MAX_NANO_CPUS_VALUE
    DEFAULT_MAX_MEMORY: ByteSize = _DEFAULT_MAX_MEMORY_VALUE
    DEFAULT_RUNTIME_TIMEOUT: int = 0

    @validator("DEFAULT_MAX_NANO_CPUS", pre=True)
    @classmethod
    def set_default_cpus_if_negative(cls, v):
        if v is None or v == "" or int(v) <= 0:
            v = _DEFAULT_MAX_NANO_CPUS_VALUE
        return v

    @validator("DEFAULT_MAX_MEMORY", pre=True)
    @classmethod
    def set_default_memory_if_negative(cls, v):
        if v is None or v == "" or int(v) <= 0:
            v = _DEFAULT_MAX_MEMORY_VALUE
        return v
