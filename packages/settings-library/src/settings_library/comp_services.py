from pydantic.types import ByteSize, NonNegativeInt
from settings_library.base import BaseCustomSettings


class CompServices(BaseCustomSettings):
    DEFAULT_MAX_NANO_CPUS: NonNegativeInt = 4 * pow(10, 9)
    DEFAULT_MAX_MEMORY: ByteSize = 2 * pow(1024, 3)  # 2 GiB
    DEFAULT_RUNTIME_TIMEOUT: int = 0
