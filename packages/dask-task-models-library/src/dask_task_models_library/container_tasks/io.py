import json
from contextlib import suppress
from pathlib import Path
from typing import Annotated, Any, TypeAlias

from models_library.basic_regex import MIME_TYPE_RE
from models_library.generics import DictModel
from models_library.services_types import ServicePortKey
from pydantic import (
    AnyUrl,
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictFloat,
    StrictInt,
    StrictStr,
)

TaskCancelEventName = "cancel_event_{}"


class PortSchema(BaseModel):
    required: bool

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "required": True,
                },
                {
                    "required": False,
                },
            ]
        },
    )


class FilePortSchema(PortSchema):
    mapping: str | None = None
    url: AnyUrl

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "mapping": "some_filename.txt",
                    "url": "sftp://some_file_url",
                    "required": True,
                },
                {
                    "required": False,
                    "url": "s3://another_file_url",
                },
            ]
        }
    )


class FileUrl(BaseModel):
    url: AnyUrl
    file_mapping: str | None = Field(
        default=None,
        description="Local file relpath name (if given), otherwise it takes the url filename",
    )
    file_mime_type: str | None = Field(
        default=None, description="the file MIME type", pattern=MIME_TYPE_RE
    )

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {"url": "https://some_file_url", "file_mime_type": "application/json"},
                {
                    "url": "https://some_file_url",
                    "file_mapping": "some_file_name.txt",
                    "file_mime_type": "application/json",
                },
            ]
        },
    )


PortValue: TypeAlias = Annotated[
    StrictBool
    | StrictInt
    | StrictFloat
    | StrictStr
    | FileUrl
    | list[Any]
    | dict[str, Any]
    | None,
    Field(union_mode="left_to_right"),
]


class TaskInputData(DictModel[ServicePortKey, PortValue]):
    model_config = ConfigDict(
        json_schema_extra={
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
    )


PortSchemaValue: TypeAlias = Annotated[
    PortSchema | FilePortSchema, Field(union_mode="left_to_right")
]


class TaskOutputDataSchema(DictModel[ServicePortKey, PortSchemaValue]):
    #
    # NOTE: Expected output data is only determined at runtime. A possibility
    # would be to create pydantic models dynamically but dask serialization
    # does not work well in that case. For that reason, the schema is
    # sent as a json-schema instead of with a dynamically-created model class
    #
    model_config = ConfigDict(
        json_schema_extra={
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
    )


class TaskOutputData(DictModel[ServicePortKey, PortValue]):
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
                file_path = output_folder / file_relpath
                if file_path.exists():
                    data[output_key] = {
                        "url": f"{output_params.url}",
                        "file_mapping": file_relpath,
                    }
                elif output_params.required:
                    msg = f"Could not locate '{file_path}' in {output_folder}"
                    raise ValueError(msg)
            elif output_key not in data and output_params.required:
                msg = f"Could not locate '{output_key}' in {output_data_file}"
                raise ValueError(msg)

        return cls.model_validate(data)

    model_config = ConfigDict(
        json_schema_extra={
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
    )
