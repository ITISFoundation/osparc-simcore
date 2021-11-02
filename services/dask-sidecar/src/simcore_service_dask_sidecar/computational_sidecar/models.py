from typing import Dict, List

from packaging import version
from pydantic import BaseModel, ByteSize, Field

LEGACY_INTEGRATION_VERSION = version.Version("0")


class ContainerHostConfig(BaseModel):
    binds: List[str] = Field(
        ..., alias="Binds", description="A list of volume bindings for this container"
    )
    init: bool = Field(
        True,
        alias="Init",
        description="Run an init inside the container that forwards signals and reaps processes. This field is omitted if empty, and the default (as configured on the daemon) is used",
    )
    memory: ByteSize = Field(..., alias="Memory", description="Memory limit in bytes")
    nano_cpus: int = Field(
        ..., alias="NanoCPUs", description="CPU quota in units of 10-9 CPUs"
    )


class DockerContainerConfig(BaseModel):
    env: List[str] = Field(..., alias="Env")
    cmd: List[str] = Field(..., alias="Cmd")
    image: str = Field(..., alias="Image")
    labels: Dict[str, str] = Field(..., alias="Labels")
    host_config: ContainerHostConfig = Field(..., alias="HostConfig")
