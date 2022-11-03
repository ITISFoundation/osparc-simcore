from typing import Optional

from packaging import version
from pydantic import BaseModel, ByteSize, Field, validator

LEGACY_INTEGRATION_VERSION = version.Version("0")


class ContainerHostConfig(BaseModel):
    binds: list[str] = Field(
        ..., alias="Binds", description="A list of volume bindings for this container"
    )
    init: bool = Field(
        default=True,
        alias="Init",
        description="Run an init inside the container that forwards signals and reaps processes. This field is omitted if empty, and the default (as configured on the daemon) is used",
    )
    memory: ByteSize = Field(..., alias="Memory", description="Memory limit in bytes")
    memory_swap: Optional[ByteSize] = Field(
        default=None,
        alias="MemorySwap",
        description="Total memory limit (memory + swap). Set as -1 to enable unlimited swap.",
    )
    nano_cpus: int = Field(
        ..., alias="NanoCPUs", description="CPU quota in units of 10-9 CPUs"
    )

    @validator("memory_swap", pre=True, always=True)
    @classmethod
    def ensure_no_memory_swap_means_no_swap(cls, v, values):
        if v is None:
            # if not set it will be the same value as memory to ensure swap is disabled
            return values["memory"]
        return v

    @validator("memory_swap")
    @classmethod
    def ensure_memory_swap_is_either_disabled_or_greater_or_equal_to_memory(
        cls, v, values
    ):
        if v <= -1:
            # if not set it will be the same value as memory to ensure swap is disabled
            return -1
        if v < values["memory"]:
            return values["memory"]
        return v


class DockerContainerConfig(BaseModel):
    env: list[str] = Field(..., alias="Env")
    cmd: list[str] = Field(..., alias="Cmd")
    image: str = Field(..., alias="Image")
    labels: dict[str, str] = Field(..., alias="Labels")
    host_config: ContainerHostConfig = Field(..., alias="HostConfig")
