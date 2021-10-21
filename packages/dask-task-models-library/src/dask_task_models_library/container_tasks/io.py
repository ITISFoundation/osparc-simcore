import json
from contextlib import suppress
from pathlib import Path
from typing import Any, Dict, Optional, Union, cast

from models_library.generics import DictModel
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
)
from typing_extensions import Annotated


class PortSchema(BaseModel):
    required: bool

    class Config:
        extra = Extra.forbid
        schema_extra: Dict[str, Any] = {
            "examples": [
                {
                    "required": True,
                },
                {
                    "required": False,
                },
            ]
        }


class FilePortSchema(PortSchema):
    mapping: Optional[str] = None
    url: AnyUrl

    class Config(PortSchema.Config):
        schema_extra = {
            "examples": [
                {
                    "mapping": "some_filename.txt",
                    "url": "ftp://some_file_url",
                    "required": True,
                },
                {
                    "required": False,
                    "url": "ftp://some_file_url",
                },
            ]
        }


class FileUrl(BaseModel):
    url: AnyUrl
    file_mapping: Optional[str] = None

    class Config:
        extra = Extra.forbid
        schema_extra = {
            "examples": [
                {
                    "url": "s3://some_file_url",
                },
                {"url": "s3://some_file_url", "file_mapping": "some_file_name.txt"},
            ]
        }


PortKey = Annotated[str, Field(regex=PROPERTY_KEY_RE)]
PortValue = Union[StrictBool, StrictInt, StrictFloat, StrictStr, FileUrl, None]
PortSchemaValue = Union[PortSchema, FilePortSchema]


class TaskInputData(DictModel[PortKey, PortValue]):
    class Config(DictModel.Config):
        schema_extra = {
            "examples": [
                {
                    "boolean_input": False,
                    "int_input": -45,
                    "float_input": 4564.45,
                    "string_input": "nobody thinks like a string",
                    "file_input": {"url": "s3://some_file_url"},
                },
            ]
        }


class TaskOutputDataSchema(DictModel[PortKey, PortSchemaValue]):
    class Config(DictModel.Config):
        schema_extra = {
            "examples": [
                {
                    "boolean_output": {"required": False},
                    "int_output": {"required": True},
                    "float_output": {"required": True},
                    "string_output": {"required": False},
                    "file_output": {
                        "required": True,
                        "url": "s3://some_file_url",
                        "mapping": "the_output_filename",
                    },
                    "optional_file_output": {
                        "required": False,
                        "url": "s3://some_file_url",
                    },
                },
            ]
        }


class TaskOutputData(DictModel[PortKey, PortValue]):
    @classmethod
    def from_task_output(
        cls, schema: TaskOutputDataSchema, output_folder: Path, output_file_ext: str
    ) -> "TaskOutputData":
        data = {}
        # try reading the outputs.json if available
        output_data_file = output_folder / output_file_ext
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
                elif output_params.required:
                    raise ValueError(
                        f"Could not locate '{file_path}' in {output_folder}"
                    )
            else:
                if output_key not in data and output_params.required:
                    raise ValueError(
                        f"Could not locate '{output_key}' in {output_data_file}"
                    )

        # NOTE: this cast is necessary to make mypy happy
        return cast(TaskOutputData, cls.parse_obj(data))

    class Config(DictModel.Config):
        schema_extra = {
            "examples": [
                {
                    "boolean_output": False,
                    "int_output": -45,
                    "float_output": 4564.45,
                    "string_output": "nobody thinks like a string",
                    "file_output": {"url": "s3://some_file_url"},
                },
            ]
        }
