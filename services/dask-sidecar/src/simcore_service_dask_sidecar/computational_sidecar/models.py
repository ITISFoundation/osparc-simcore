from packaging import version
from pydantic import BaseModel, ByteSize, Field

LEGACY_INTEGRATION_VERSION = version.Version("0")

# CHANGELOG:
# INPUT_FOLDER/input.json --> INPUT_FOLDER/inputs.json
# OUTPUT_FOLDER/output.json --> OUTPUT_FOLDER/outputs.json
# logs folder removed since docker already provides a logging system
VERSION_1_0_0 = version.Version("1.0.0")

# CHANGELOG:
# removes flat filesystem
# /inputs/inputs.json --> contains non file data (strings, numbers, ...)
# /inputs/input_1/... -> contains file data for input_1
# /inputs/input_2/... -> contains file data for input_2
# /outputs/outputs.json --> contains non file data
# /outputs/output_1 --> contains non file data for output_1
# /outputs/output_2 --> contains non file data for output_2
VERSION_1_1_0 = version.Version("1.1.0")


class ContainerHostConfig(BaseModel):
    binds: list[str] = Field(
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
    env: list[str] = Field(..., alias="Env")
    cmd: list[str] = Field(..., alias="Cmd")
    image: str = Field(..., alias="Image")
    labels: dict[str, str] = Field(..., alias="Labels")
    host_config: ContainerHostConfig = Field(..., alias="HostConfig")
