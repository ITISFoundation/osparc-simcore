import json
from contextlib import suppress
from pathlib import Path
from typing import (
    Any,
    Dict,
    ItemsView,
    KeysView,
    Optional,
    Tuple,
    Type,
    Union,
    ValuesView,
)

from models_library.services import PROPERTY_KEY_RE
from pydantic import (
    AnyUrl,
    BaseModel,
    Extra,
    Field,
    StrictBool,
    StrictFloat,
    StrictInt,
    StrictStr,
    create_model,
)
from pydantic.fields import FieldInfo
from typing_extensions import Annotated


class TaskBaseModel(BaseModel):
    class Config:
        extra = Extra.forbid


class DynamicTaskInputData(TaskBaseModel):
    ...


class DynamicTaskOutputData(TaskBaseModel):
    ...


InputTypes = Union[
    Type[StrictBool], Type[StrictInt], Type[StrictFloat], Type[StrictStr], Type[AnyUrl]
]


class FileUrl(BaseModel):
    url: AnyUrl
    file_mapping: Optional[str] = None


PortKey = Annotated[str, Field(regex=PROPERTY_KEY_RE)]


def create_inputs_signature(
    name: str,
    input_data: Dict[
        PortKey,
        Tuple[InputTypes, FieldInfo],
    ],
) -> Type[DynamicTaskInputData]:
    return create_model(
        name, **input_data, __module__=__name__, __base__=DynamicTaskInputData
    )


class PortSchema(BaseModel):
    required: bool

    class Config:
        extra = Extra.forbid


class FilePortSchema(PortSchema):
    mapping: Optional[str] = None
    url: AnyUrl


PortValue = Union[StrictBool, StrictInt, StrictFloat, StrictStr, FileUrl, None]
PortSchemaValue = Union[PortSchema, FilePortSchema]


class TaskInputData(BaseModel):
    __root__: Dict[PortKey, PortValue]

    def items(self) -> ItemsView[PortKey, PortValue]:
        return self.__root__.items()


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

    def values(self) -> ValuesView[PortValue]:
        return self.__root__.values()

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
                    data[output_key] = {
                        "url": f"{output_params.url}",
                        "file_mapping": file_path.name,
                    }

        return cls.parse_obj(data)
