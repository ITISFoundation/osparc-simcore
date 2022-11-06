from copy import deepcopy
from typing import Any, Literal, Optional, Union

from pydantic import schema_of

from ..services import ServiceInput, ServiceOutput
from ..services_constants import PROPERTY_TYPE_TO_PYTHON_TYPE_MAP

PortKindStr = Literal["input", "output"]

_PROPERTY_TYPE_TO_SCHEMAS = {
    property_type: schema_of(python_type, title=property_type.capitalize())
    for property_type, python_type in PROPERTY_TYPE_TO_PYTHON_TYPE_MAP.items()
}


def get_service_io_json_schema(
    io: Union[ServiceInput, ServiceOutput]
) -> Optional[dict[str, Any]]:
    """Get json-schema for a i/o service

    For legacy metadata with property_type = integer, etc ... , it applies a conversion
    """
    if io.content_schema:
        return deepcopy(io.content_schema)

    # converts legacy
    if schema := _PROPERTY_TYPE_TO_SCHEMAS.get(io.property_type):
        schema = deepcopy(schema)

        # updates schema-doc, i.e description and title
        schema["title"] = io.label
        if io.label != io.description:
            schema["description"] = io.description

        # new x_unit custom field in json-schema
        if io.unit:
            schema["x_unit"] = io.unit

        # updates default
        default = getattr(io, "default_value", None)
        if default is not None:
            schema["default"] = default
        return schema

    return None
