import mimetypes
from copy import deepcopy
from typing import Any, Literal

from pydantic import TypeAdapter

from ..services import ServiceInput, ServiceOutput
from ..services_regex import PROPERTY_TYPE_TO_PYTHON_TYPE_MAP

PortKindStr = Literal["input", "output"]
JsonSchemaDict = dict[str, Any]


_PROPERTY_TYPE_TO_SCHEMAS = {
    property_type: {
        **TypeAdapter(python_type).json_schema(),
        "title": property_type.capitalize(),
    }
    for property_type, python_type in PROPERTY_TYPE_TO_PYTHON_TYPE_MAP.items()
}


def guess_media_type(io: ServiceInput | ServiceOutput) -> str:
    # SEE https://docs.python.org/3/library/mimetypes.html
    # SEE https://www.iana.org/assignments/media-types/media-types.xhtml
    media_type = io.property_type.removeprefix("data:")
    if media_type == "*/*" and io.file_to_key_map:
        filename = next(iter(io.file_to_key_map.keys()))
        guessed_media_type, _ = mimetypes.guess_type(filename)
        if guessed_media_type is None:
            return "*/*"
        return guessed_media_type
    return media_type


def update_schema_doc(schema: dict[str, Any], port: ServiceInput | ServiceOutput):
    schema["title"] = port.label
    if port.label != port.description:
        schema["description"] = port.description
    return schema


def get_service_io_json_schema(
    port: ServiceInput | ServiceOutput,
) -> JsonSchemaDict | None:
    """Get json-schema for a i/o service

    For legacy metadata with property_type = integer, etc ... , it applies a conversion

    NOTE: For the moment, this is a free function. It migh become in the future a member
    of BaseServiceIO once we proceed to a full deprecation of legacy fields like units, etc
    """
    if port.content_schema:
        # NOTE this schema was already validated in BaseServiceIOModel
        return deepcopy(port.content_schema)

    # converts legacy
    if schema := _PROPERTY_TYPE_TO_SCHEMAS.get(port.property_type):
        schema = deepcopy(schema)

        # updates schema-doc, i.e description and title
        update_schema_doc(schema=schema, port=port)

        # new x_unit custom field in json-schema
        if port.unit:
            schema["x_unit"] = port.unit

        # updates default
        default = getattr(port, "default_value", None)
        if default is not None:
            schema["default"] = default
        return schema

    return None
