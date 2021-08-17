from pydantic import ByteSize, NonNegativeInt, validator
from settings_library.base import BaseCustomSettings


class CompServices(BaseCustomSettings):
    DEFAULT_MAX_NANO_CPUS: NonNegativeInt = 4 * pow(10, 9)
    DEFAULT_MAX_MEMORY: ByteSize = 2 * pow(1024, 3)  # 2 GiB
    DEFAULT_RUNTIME_TIMEOUT: int = 0

    @validator("DEFAULT_MAX_NANO_CPUS", pre=True)
    @classmethod
    def set_default_cpus_if_negative(cls, v):
        if v is None or v == "" or int(v) <= 0:
            v = 4 * pow(10, 9)
        return v

    @validator("DEFAULT_MAX_MEMORY", pre=True)
    @classmethod
    def set_default_memory_if_negative(cls, v):
        if v is None or v == "" or int(v) <= 0:
            v = 2 * pow(1024, 3)
        return v
