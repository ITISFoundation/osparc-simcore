import json
from contextlib import suppress
from pathlib import Path
from typing import Any, ClassVar, Union, cast

from models_library.basic_regex import MIME_TYPE_RE
from models_library.generics import DictModel
from models_library.services import PROPERTY_KEY_RE
from pydantic import (
    AnyUrl,
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictFloat,
    StrictInt,
    StrictStr,
    StringConstraints,
)
from typing_extensions import Annotated

TaskCancelEventName = "cancel_event_{}"


class PortSchema(BaseModel):
    required: bool
    model_config = ConfigDict(extra="forbid")


class FilePortSchema(PortSchema):
    mapping: str | None = None
    url: AnyUrl

    # TODO[pydantic]: The `Config` class inherits from another class, please create the `model_config` manually.
    # Check https://docs.pydantic.dev/dev-v2/migration/#changes-to-config for more information.
    class Config(PortSchema.Config):
        schema_extra: ClassVar[dict[str, Any]] = {
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


class FileUrl(BaseModel):
    url: AnyUrl
    file_mapping: str | None = Field(
        default=None,
        description="Local file relpath name (if given), otherwise it takes the url filename",
    )
    file_mime_type: str | None = Field(
        default=None, description="the file MIME type", pattern=MIME_TYPE_RE
    )
    model_config = ConfigDict(extra="forbid")


PortKey = Annotated[str, StringConstraints(pattern=PROPERTY_KEY_RE)]
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
    # TODO[pydantic]: The `Config` class inherits from another class, please create the `model_config` manually.
    # Check https://docs.pydantic.dev/dev-v2/migration/#changes-to-config for more information.
    class Config(DictModel.Config):
        schema_extra: ClassVar[dict[str, Any]] = {
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
    # TODO[pydantic]: The `Config` class inherits from another class, please create the `model_config` manually.
    # Check https://docs.pydantic.dev/dev-v2/migration/#changes-to-config for more information.
    class Config(DictModel.Config):
        schema_extra: ClassVar[dict[str, Any]] = {
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

        # NOTE: this cast is necessary to make mypy happy
        return cast(TaskOutputData, cls.parse_obj(data))

    # TODO[pydantic]: The `Config` class inherits from another class, please create the `model_config` manually.
    # Check https://docs.pydantic.dev/dev-v2/migration/#changes-to-config for more information.
    class Config(DictModel.Config):
        schema_extra: ClassVar[dict[str, Any]] = {
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
