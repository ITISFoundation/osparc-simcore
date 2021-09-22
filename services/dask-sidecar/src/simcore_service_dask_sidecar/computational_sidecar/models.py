import json
from contextlib import suppress
from pathlib import Path
from typing import Any, Dict, ItemsView, KeysView, List, Optional, Union

from models_library.services import PROPERTY_KEY_RE
from pydantic import (
    AnyUrl,
    BaseModel,
    ByteSize,
    Extra,
    Field,
    StrictBool,
    StrictFloat,
    StrictInt,
    StrictStr,
)
from pydantic.types import SecretStr
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


class PortSchema(BaseModel):
    required: bool

    class Config:
        extra = Extra.forbid


class FilePortSchema(PortSchema):
    mapping: Optional[str] = None


PortSchemaValue = Union[PortSchema, FilePortSchema]


class TaskOutputDataSchema(BaseModel):
    __root__: Dict[PortKey, PortSchemaValue]

    def __getitem__(self, k: PortKey) -> PortSchemaValue:
        return self.__root__.__getitem__(k)

    def __setitem__(self, k: PortKey, v: PortSchemaValue) -> None:
        self.__root__.__setitem__(k, v)

    def items(self) -> ItemsView[PortKey, PortSchemaValue]:
        return self.__root__.items()

    def keys(self) -> KeysView[PortKey]:
        return self.__root__.keys()

    def __iter__(self) -> Any:
        return self.__root__.__iter__()


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

    @classmethod
    def from_task_output(
        cls, schema: TaskOutputDataSchema, output_folder: Path
    ) -> "TaskOutputData":
        data = {}
        # try reading the outputs.json if available
        output_data_file = output_folder / "outputs.json"
        if output_data_file.exists():
            with suppress(json.JSONDecodeError):
                # in case the loading throw, then the data will be missing
                # and we will get a validation error when reading the file in
                data = json.loads(output_data_file.read_text())

        for output_key, output_params in schema.items():
            if isinstance(output_params, FilePortSchema):
                file_path = output_folder / (output_params.mapping or output_key)
                if file_path.exists():
                    data[output_key] = {"url": f"file://{file_path.name}"}

        return cls.parse_obj(data)
