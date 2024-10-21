from typing import Annotated, Any, TypeAlias

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictFloat,
    StrictInt,
    StringConstraints,
    ValidationInfo,
    field_validator,
)

from .services_constants import ANY_FILETYPE
from .services_regex import PROPERTY_TYPE_RE
from .services_types import FileName, ServicePortKey
from .services_ui import Widget
from .utils.json_schema import (
    InvalidJsonSchema,
    any_ref_key,
    jsonschema_validate_schema,
)

PropertyTypeStr: TypeAlias = Annotated[str, StringConstraints(pattern=PROPERTY_TYPE_RE)]


class BaseServiceIOModel(BaseModel):
    """
    Base class for service input/outputs
    """

    ## management

    ### human readable descriptors
    display_order: float | None = Field(
        None,
        alias="displayOrder",
        deprecated=True,
        description="DEPRECATED: new display order is taken from the item position. This will be removed.",
    )

    label: str = Field(..., description="short name for the property", examples=["Age"])
    description: str = Field(
        ...,
        description="description of the property",
        examples=["Age in seconds since 1970"],
    )

    # mathematical and physics descriptors
    property_type: PropertyTypeStr = Field(
        ...,
        alias="type",
        description="data type expected on this input glob matching for data type is allowed",
        examples=[
            "number",
            "boolean",
            ANY_FILETYPE,
            "data:text/*",
            "data:[image/jpeg,image/png]",
            "data:application/json",
            "data:application/json;schema=https://my-schema/not/really/schema.json",
            "data:application/vnd.ms-excel",
            "data:text/plain",
            "data:application/hdf5",
            "data:application/edu.ucdavis@ceclancy.xyz",
        ],
    )

    content_schema: dict[str, Any] | None = Field(
        None,
        description="jsonschema of this input/output. Required when type='ref_contentSchema'",
        alias="contentSchema",
    )

    # value
    file_to_key_map: dict[FileName, ServicePortKey] | None = Field(
        None,
        alias="fileToKeyMap",
        description="Place the data associated with the named keys in files",
        examples=[{"dir/input1.txt": "key_1", "dir33/input2.txt": "key2"}],
    )

    unit: str | None = Field(
        None,
        description="Units, when it refers to a physical quantity",
        deprecated=True,  # add x_unit in content_schema instead
    )

    model_config = ConfigDict(extra="forbid")

    @field_validator("content_schema")
    @classmethod
    def _check_type_is_set_to_schema(cls, v, info: ValidationInfo):
        if (
            v is not None
            and (ptype := info.data["property_type"]) != "ref_contentSchema"
        ):
            msg = f"content_schema is defined but set the wrong type. Expected type=ref_contentSchema but got ={ptype}."
            raise ValueError(msg)
        return v

    @field_validator("content_schema")
    @classmethod
    def _check_valid_json_schema(cls, v):
        if v is not None:
            try:
                jsonschema_validate_schema(schema=v)

                if any_ref_key(v):
                    # SEE https://github.com/ITISFoundation/osparc-simcore/issues/3030
                    msg = "Schemas with $ref are still not supported"
                    raise ValueError(msg)

            except InvalidJsonSchema as err:
                failed_path = "->".join(map(str, err.path))
                msg = f"Invalid json-schema at {failed_path}: {err.message}"
                raise ValueError(msg) from err
        return v

    @classmethod
    def _from_json_schema_base_implementation(
        cls, port_schema: dict[str, Any]
    ) -> dict[str, Any]:
        description = port_schema.pop("description", port_schema["title"])
        return {
            "label": port_schema["title"],
            "description": description,
            "type": "ref_contentSchema",
            "contentSchema": port_schema,
        }


class ServiceInput(BaseServiceIOModel):
    """
    Metadata on a service input port
    """

    default_value: StrictBool | StrictInt | StrictFloat | str | None = Field(
        None,
        alias="defaultValue",
        examples=["Dog", True],
        deprecated=True,  # Use content_schema defaults instead
    )

    widget: Widget | None = Field(
        None,
        description="custom widget to use instead of the default one determined from the data-type",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                # file-wo-widget:
                {
                    "displayOrder": 1,
                    "label": "Input files - file-wo-widget",
                    "description": "Files downloaded from service connected at the input",
                    "type": ANY_FILETYPE,
                },
                # v2
                {
                    "displayOrder": 2,
                    "label": "Sleep Time - v2",
                    "description": "Time to wait before completion",
                    "type": "number",
                    "defaultValue": 0,
                    "unit": "second",
                    "widget": {"type": "TextArea", "details": {"minHeight": 3}},
                },
                # latest:
                {
                    "label": "Sleep Time - latest",
                    "description": "Time to wait before completion",
                    "type": "number",
                    "defaultValue": 0,
                    "unit": "second",
                    "widget": {"type": "TextArea", "details": {"minHeight": 3}},
                },
                {
                    "label": "array_numbers",
                    "description": "Some array of numbers",
                    "type": "ref_contentSchema",
                    "contentSchema": {
                        "title": "list[number]",
                        "type": "array",
                        "items": {"type": "number"},
                    },
                },
                {
                    "label": "my_object",
                    "description": "Some object",
                    "type": "ref_contentSchema",
                    "contentSchema": {
                        "title": "an object named A",
                        "type": "object",
                        "properties": {
                            "i": {"title": "Int", "type": "integer", "default": 3},
                            "b": {"title": "Bool", "type": "boolean"},
                            "s": {"title": "Str", "type": "string"},
                        },
                        "required": ["b", "s"],
                    },
                },
            ],
        },
    )

    @classmethod
    def from_json_schema(cls, port_schema: dict[str, Any]) -> "ServiceInput":
        """Creates input port model from a json-schema"""
        data = cls._from_json_schema_base_implementation(port_schema)
        return cls.model_validate(data)


class ServiceOutput(BaseServiceIOModel):
    widget: Widget | None = Field(
        None,
        description="custom widget to use instead of the default one determined from the data-type",
        deprecated=True,
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "displayOrder": 2,
                    "label": "Time Slept",
                    "description": "Time the service waited before completion",
                    "type": "number",
                },
                {
                    "displayOrder": 2,
                    "label": "Time Slept - units",
                    "description": "Time with units",
                    "type": "number",
                    "unit": "second",
                },
                {
                    "label": "Time Slept - w/o displayorder",
                    "description": "Time without display order",
                    "type": "number",
                    "unit": "second",
                },
                {
                    "label": "Output file 1",
                    "displayOrder": 4.0,
                    "description": "Output file uploaded from the outputs folder",
                    "type": ANY_FILETYPE,
                },
            ]
        },
    )

    @classmethod
    def from_json_schema(cls, port_schema: dict[str, Any]) -> "ServiceOutput":
        """Creates output port model from a json-schema"""
        data = cls._from_json_schema_base_implementation(port_schema)
        return cls.model_validate(data)
