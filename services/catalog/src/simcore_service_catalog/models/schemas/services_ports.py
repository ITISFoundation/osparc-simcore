import mimetypes
from copy import deepcopy
from typing import Any, Literal, Optional, Union

from models_library.basic_regex import PUBLIC_VARIABLE_NAME_RE
from models_library.services import ServiceInput, ServiceOutput
from models_library.services_constants import PROPERTY_TYPE_TO_PYTHON_TYPE_MAP
from pydantic import BaseModel, Field, schema_of

PortKindStr = Literal["input", "output"]

_PROPERTY_TYPE_TO_SCHEMAS = {
    property_type: schema_of(python_type, title=property_type.capitalize())
    for property_type, python_type in PROPERTY_TYPE_TO_PYTHON_TYPE_MAP.items()
}


def _update_schema_doc(schema: dict[str, Any], io: Union[ServiceInput, ServiceOutput]):
    schema["title"] = io.label
    if io.label != io.description:
        schema["description"] = io.description
    return schema


def _property_type_to_schema(
    io: Union[ServiceInput, ServiceOutput]
) -> Optional[dict[str, Any]]:
    """Converts (if possible) BaseServiceIOModel.property_type into json schema, otherwise None"""
    if schema := _PROPERTY_TYPE_TO_SCHEMAS.get(io.property_type):
        schema = deepcopy(schema)
        # description and title
        _update_schema_doc(schema, io)

        # default
        default = getattr(io, "default_value", None)
        if default is not None:
            schema["default"] = default
        return schema
    return None


def _guess_media_type(io: Union[ServiceInput, ServiceOutput]) -> str:
    # SEE https://docs.python.org/3/library/mimetypes.html
    # SEE https://www.iana.org/assignments/media-types/media-types.xhtml
    media_type = io.property_type.removeprefix("data:")
    if media_type == "*/*" and io.file_to_key_map:
        filename = list(io.file_to_key_map.keys())[0]
        media_type, _ = mimetypes.guess_type(filename)
        if media_type is None:
            media_type = "*/*"
    return media_type


#
# Model -------------------------------------------------------------------------------
#


class ServicePortGet(BaseModel):
    key: str = Field(
        ...,
        description="port identifier name",
        regex=PUBLIC_VARIABLE_NAME_RE,
        title="Key name",
    )
    kind: PortKindStr
    content_media_type: Optional[str] = None
    content_schema: Optional[dict[str, Any]] = Field(
        None,
        description="jsonschema for the port's value. SEE https://json-schema.org/understanding-json-schema/",
    )

    class Config:
        schema_extra = {
            "example": {
                "key": "input_1",
                "kind": "input",
                "content_schema": {
                    "title": "Sleep interval",
                    "type": "integer",
                    "x_unit": "second",
                    "minimum": 0,
                    "maximum": 5,
                },
            }
        }

    @classmethod
    def from_service_io(
        cls,
        kind: PortKindStr,
        key: str,
        io: Union[ServiceInput, ServiceOutput],
    ) -> "ServicePortGet":
        kwargs: dict[str, Any] = {"key": key, "kind": kind}

        # Convert old format into schemas
        schema = io.content_schema
        if not schema:
            schema = _property_type_to_schema(io)

        # Deduce media_type
        if io.property_type.startswith("data:"):
            kwargs["content_media_type"] = _guess_media_type(io)
            # Based on https://swagger.io/docs/specification/describing-request-body/file-upload/
            schema = _update_schema_doc({"type": "string"}, io)

        kwargs["content_schema"] = schema
        return cls(**kwargs)
