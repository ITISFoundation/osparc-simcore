import json
from contextlib import suppress
from pathlib import Path
from typing import Any, Optional, Union, cast

from models_library.basic_regex import MIME_TYPE_RE
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
from pydantic.types import constr

TaskCancelEventName = "cancel_event_{}"


class PortSchema(BaseModel):
    required: bool

    class Config:
        extra = Extra.forbid
        schema_extra: dict[str, Any] = {
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
                    "url": "s3://another_file_url",
                },
            ]
        }


class FileUrl(BaseModel):
    url: AnyUrl
    file_mapping: Optional[str] = Field(
        None,
        description="Local file relpath name (if given), otherwise it takes the url filename",
    )
    file_mime_type: Optional[str] = Field(
        None, description="the file MIME type", regex=MIME_TYPE_RE
    )

    class Config:
        extra = Extra.forbid
        schema_extra = {
            "examples": [
                {"url": "https://some_file_url", "file_mime_type": "application/json"},
                {
                    "url": "https://some_file_url",
                    "file_mapping": "some_file_name.txt",
                    "file_mime_type": "application/json",
                },
            ]
        }


PortKey = constr(regex=PROPERTY_KEY_RE)
PortValue = Union[
    StrictBool,
    StrictInt,
    StrictFloat,
    StrictStr,
    FileUrl,
    list[Any],
    dict[str, Any],
    None,
]


class TaskInputData(DictModel[PortKey, PortValue]):
    class Config(DictModel.Config):
        schema_extra = {
            "examples": [
                {
                    "boolean_input": False,
                    "int_input": -45,
                    "float_input": 4564.45,
                    "string_input": "nobody thinks like a string",
                    "file_input": {"url": "s3://thatis_file_url"},
                },
            ]
        }


PortSchemaValue = Union[PortSchema, FilePortSchema]


class TaskOutputDataSchema(DictModel[PortKey, PortSchemaValue]):
    #
    # NOTE: Expected output data is only determined at runtime. A possibility
    # would be to create pydantic models dynamically but dask serialization
    # does not work well in that case. For that reason, the schema is
    # sent as a json-schema instead of with a dynamically-created model class
    #
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
                        "url": "https://some_file_url",
                        "mapping": "the_output_filename",
                    },
                    "optional_file_output": {
                        "required": False,
                        "url": "s3://one_file_url",
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
                # NOTE: The suppression here is ok, since if the data is empty,
                # there will be a validation error anyway
                data = json.loads(output_data_file.read_text())

        for output_key, output_params in schema.items():
            if isinstance(output_params, FilePortSchema):
                file_relpath = output_params.mapping or output_key
                # TODO: file_path is built here, saved truncated in file_mapping and
                # then rebuild again int _retrieve_output_data. Review.
                file_path = output_folder / file_relpath
                if file_path.exists():
                    data[output_key] = {
                        "url": f"{output_params.url}",
                        "file_mapping": file_relpath,
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
                    "file_output": {"url": "s3://yet_another_file_url"},
                },
            ]
        }
