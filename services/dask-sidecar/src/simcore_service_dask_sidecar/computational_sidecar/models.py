from typing import Any, Dict, ItemsView, KeysView, List, Optional, Union

from models_library.services import PROPERTY_KEY_RE
from pydantic import (
    AnyUrl,
    BaseModel,
    ByteSize,
    Field,
    StrictBool,
    StrictFloat,
    StrictInt,
    StrictStr,
)
from typing_extensions import Annotated


class ContainerHostConfig(BaseModel):
    # autoremove: bool = Field(
    #     True,
    #     alias="AutoRemove",
    #     description="Automatically remove the container when the container's process exits. This has no effect if RestartPolicy is set",
    # )
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


class FileUrl(BaseModel):
    url: AnyUrl
    file_mapping: Optional[str] = None


PortKey = Annotated[str, Field(regex=PROPERTY_KEY_RE)]
PortValue = Union[StrictBool, StrictInt, StrictFloat, StrictStr, FileUrl]


class TaskInputData(BaseModel):
    __root__: Dict[PortKey, PortValue]

    def items(self) -> ItemsView[PortKey, PortValue]:
        return self.__root__.items()


class TaskOutputData(BaseModel):
    __root__: Dict[PortKey, PortValue]

    def __getitem__(self, k: PortKey) -> PortValue:
        return self.__root__.__getitem__(k)

    def __setitem__(self, k: PortKey, v: PortValue) -> None:
        self.__root__.__setitem__(k, v)

    def items(self) -> ItemsView[PortKey, PortValue]:
        return self.__root__.items()

    def keys(self) -> KeysView[PortKey]:
        return self.__root__.keys()

    def __iter__(self) -> Any:
        return self.__root__.__iter__()
